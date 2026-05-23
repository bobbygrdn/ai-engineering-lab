"""Built-in pre-invoke hooks: simple rate limiter and role checks."""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from .engine import HookAbort
from modules.utils.interactions import record_event


class SimpleRateLimiter:
    def __init__(self, max_calls: int, window_seconds: int):
        self.max_calls = int(max_calls)
        self.window = int(window_seconds)
        # map key -> list of timestamps
        self._calls: Dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        q = self._calls.setdefault(key, [])
        # drop old
        cutoff = now - self.window
        while q and q[0] < cutoff:
            q.pop(0)
        if len(q) >= self.max_calls:
            return False
        q.append(now)
        return True


def rate_limit_hook_factory(max_calls: int = 60, window_seconds: int = 60) -> Callable[[Dict[str, Any], Dict[str, Any], Optional[str]], Any]:
    limiter = SimpleRateLimiter(max_calls=max_calls, window_seconds=window_seconds)

    def hook(manifest: Dict[str, Any], args: Dict[str, Any], caller: Optional[str]) -> None:
        key = caller or "anonymous"
        # include tool name for per-tool limits
        tool = manifest.get("name", "unknown")
        full_key = f"tool:{tool}:caller:{key}"
        allowed = limiter.allow(full_key)
        record_event("hook_rate_limit_check", {"tool": tool, "caller": key, "allowed": allowed})
        if not allowed:
            raise HookAbort("rate limit exceeded", retryable=True)

    return hook


def role_check_token_per_tool_factory(auth_manager, state_store, allowed_roles: list[str], tool_name: str):
    """Create a hook bound to a specific tool that validates caller token (JWT `sub`) or falls back to username.

    - `auth_manager` must implement `decode_token(token, expected_type)` returning payload with `sub`.
    - `state_store` must implement `get_roles_for_user_id` and `get_roles_for_username`.
    """

    def hook(manifest: Dict[str, Any], args: Dict[str, Any], caller: Optional[str]) -> None:
        # only enforce for the specific tool
        if manifest.get("name") != tool_name:
            return None

        required = allowed_roles
        if not required:
            return None

        if not caller:
            raise HookAbort("caller missing", retryable=False)

        user_id = None
        # try to decode as access token
        try:
            payload = auth_manager.decode_token(caller, expected_type="access")
            sub = payload.get("sub")
            if sub is not None:
                user_id = int(sub)
        except Exception:
            user_id = None

        if user_id is None:
            # require token-derived identity for this strict per-tool hook
            raise HookAbort("caller must present a valid access token", retryable=False)

        roles = state_store.get_roles_for_user_id(user_id) or []

        if not set(roles).intersection(set(required)):
            raise HookAbort("caller missing required role", retryable=False)

    return hook


def role_check_hook_factory(role_db: Dict[str, list[str]]) -> Callable[[Dict[str, Any], Dict[str, Any], Optional[str]], Any]:
    """Create a hook that enforces `manifest['allowed_roles']` against role_db mapping caller->roles."""

    def hook(manifest: Dict[str, Any], args: Dict[str, Any], caller: Optional[str]) -> None:
        required = manifest.get("allowed_roles")
        if not required:
            return None
        if not caller:
            raise HookAbort("caller missing", retryable=False)
        roles = set(role_db.get(caller, []))
        if not roles.intersection(set(required)):
            raise HookAbort("caller missing required role", retryable=False)

    return hook


def role_check_state_store_factory(state_store) -> Callable[[Dict[str, Any], Dict[str, Any], Optional[str]], Any]:
    """Create a hook that enforces `manifest['allowed_roles']` using the provided state_store.

    The hook will call `state_store.get_roles_for_username(caller)` to obtain roles.
    """

    def hook(manifest: Dict[str, Any], args: Dict[str, Any], caller: Optional[str]) -> None:
        required = manifest.get("allowed_roles")
        if not required:
            return None
        if not caller:
            raise HookAbort("caller missing", retryable=False)
        roles = set(state_store.get_roles_for_username(caller) or [])
        if not roles.intersection(set(required)):
            raise HookAbort("caller missing required role", retryable=False)

    return hook
