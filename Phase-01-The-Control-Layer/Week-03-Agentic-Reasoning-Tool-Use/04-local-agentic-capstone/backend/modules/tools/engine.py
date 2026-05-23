"""Deterministic tool invocation engine with strict validation and audit logging."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Dict, Optional

from .validator import ManifestValidationError, validate_args, validate_manifest
from .invoke_middleware import enforce_framed_user_data
from modules.utils.interactions import record_event


class ToolEngine:
    def __init__(self):
        # registry: tool_name -> (manifest, callable)
        self._registry: Dict[str, tuple[Dict[str, Any], Callable]] = {}
        # pre-invoke hooks: list of callables(manifest, args, caller) -> None | dict
        # If a hook returns a dict, it's treated as the new args. Hooks may also raise HookAbort.
        self._pre_invoke_hooks: list[Callable[[Dict[str, Any], Dict[str, Any], Optional[str]], Any]] = []
        self._auth_manager = None
        self._enforce_token_for_all = False

    def register_tool(self, manifest: Dict[str, Any], func: Callable) -> None:
        # validate manifest handshake strictly
        validate_manifest(manifest)
        name = manifest["name"]
        key = self._manifest_key(manifest)
        record_event("tool_registered", {"tool": name, "manifest_key": key})
        self._registry[name] = (manifest, func)

    # Pre-invoke hook API
    def register_pre_invoke_hook(self, hook: Callable[[Dict[str, Any], Dict[str, Any], Optional[str]], Any], prepend: bool = False) -> None:
        """Register a pre-invoke hook. Hooks are called with (manifest, args, caller).

        A hook may:
          - return None (no change)
          - return a dict to replace/modify `args`
          - raise HookAbort to abort invocation with structured error
        """
        if prepend:
            self._pre_invoke_hooks.insert(0, hook)
        else:
            self._pre_invoke_hooks.append(hook)

    def set_auth_manager(self, auth_manager) -> None:
        """Provide an AuthManager instance to the engine so hooks or enforcement can decode tokens."""
        self._auth_manager = auth_manager

    def require_token_for_all_invocations(self, enable: bool = True) -> None:
        """If enabled, engine.invoke will require a valid access token as `caller` for all invocations."""
        self._enforce_token_for_all = bool(enable)

    def unregister_pre_invoke_hook(self, hook: Callable[[Dict[str, Any], Dict[str, Any], Optional[str]], Any]) -> None:
        try:
            self._pre_invoke_hooks.remove(hook)
        except ValueError:
            pass

    def clear_pre_invoke_hooks(self) -> None:
        self._pre_invoke_hooks.clear()

    def _manifest_key(self, manifest: Dict[str, Any]) -> str:
        s = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    def invoke(self, tool_name: str, args: Dict[str, Any], caller: Optional[str] = None) -> Dict[str, Any]:
        """Invoke a registered tool deterministically.

        Returns a dict with keys: success(bool), result (on success), error (on failure), retryable(bool).
        """
        if tool_name not in self._registry:
            record_event("tool_invoke_failed", {"tool": tool_name, "reason": "not_registered", "caller": caller})
            return {"success": False, "error": "tool not registered", "retryable": False}

        manifest, func = self._registry[tool_name]

        # caller check (principle of least privilege)
        allowed_callers = manifest.get("allowed_callers")
        if allowed_callers:
            if caller is None or caller not in allowed_callers:
                record_event("audit_alert", {"tool": tool_name, "caller": caller, "reason": "caller_not_allowed"})
                return {"success": False, "error": "caller not authorized for this tool", "retryable": False}

        # Enforce token-for-all if configured: require an access token string as caller and validate it
        if getattr(self, "_enforce_token_for_all", False):
            if not caller:
                record_event("audit_alert", {"tool": tool_name, "caller": caller, "reason": "missing_token"})
                return {"success": False, "error": "missing_access_token", "retryable": False}
            if not getattr(self, "_auth_manager", None):
                record_event("audit_alert", {"tool": tool_name, "caller": caller, "reason": "no_auth_manager"})
                return {"success": False, "error": "no_auth_manager_configured", "retryable": False}
            try:
                # validate token type; do not rely on payload here beyond raising on invalid
                self._auth_manager.decode_token(caller, expected_type="access")
            except Exception as e:
                record_event("audit_alert", {"tool": tool_name, "caller": caller, "reason": "invalid_token", "detail": str(e)})
                return {"success": False, "error": "invalid_access_token", "retryable": False}

        # enforce middleware checks (defense-in-depth)
        try:
            enforce_framed_user_data(manifest, args)
        except Exception as e:
            record_event("audit_alert", {"tool": tool_name, "caller": caller, "reason": "unframed_user_data", "detail": str(e)})
            return {"success": False, "error": "unframed_user_data", "details": str(e), "retryable": True}

        # run pre-invoke hooks (they may modify args or abort)
        try:
            for hook in list(self._pre_invoke_hooks):
                res = hook(manifest, args, caller)
                if isinstance(res, dict):
                    # treat returned dict as new args
                    args = res
        except HookAbort as h:
            record_event("audit_alert", {"tool": tool_name, "caller": caller, "reason": "hook_abort", "detail": h.message})
            return {"success": False, "error": h.message, "retryable": h.retryable}
        except Exception as e:
            record_event("audit_alert", {"tool": tool_name, "caller": caller, "reason": "hook_exception", "detail": str(e)})
            return {"success": False, "error": "pre_invoke_hook_failed", "details": str(e), "retryable": True}

        # validate args strictly
        try:
            validate_args(manifest, args)
        except ManifestValidationError as e:
            # audit-only alert (do not perform side-effectful op)
            record_event("audit_alert", {"tool": tool_name, "caller": caller, "errors": e.errors})
            # return structured validation failure and mark retryable so AI can adapt
            return {"success": False, "error": "validation_failed", "details": e.errors, "retryable": True}

        # Log the invocation intent (deterministic, auditable)
        record_event("tool_invoke", {"tool": tool_name, "caller": caller, "args": args})

        try:
            result = func(args)
            record_event("tool_result", {"tool": tool_name, "caller": caller, "result_summary": str(result)})
            return {"success": True, "result": result, "retryable": False}
        except Exception as e:
            record_event("tool_error", {"tool": tool_name, "caller": caller, "error": str(e)})
            return {"success": False, "error": str(e), "retryable": True}


class HookAbort(Exception):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.retryable = retryable


engine = ToolEngine()
