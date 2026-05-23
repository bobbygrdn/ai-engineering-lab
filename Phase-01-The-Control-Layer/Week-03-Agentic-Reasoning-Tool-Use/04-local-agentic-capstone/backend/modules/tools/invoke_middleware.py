"""Middleware helpers for tool invocation enforcement (defense-in-depth)."""
from __future__ import annotations

from typing import Any, Dict
from modules.tools.framing import FramingError


def _is_framed_string(s: str) -> bool:
    s = s.strip()
    return s.startswith("<user_data>") and s.endswith("</user_data>")


def enforce_framed_user_data(manifest: Dict[str, Any], args: Dict[str, Any]) -> None:
    """Raise FramingError if manifest requires framed user data but args aren't framed.

    Manifest convention: include boolean `requires_framed_user_data` at top-level.
    """
    if not manifest.get("requires_framed_user_data"):
        return

    # inspect string args for unframed content
    for k, v in args.items():
        if isinstance(v, str):
            if not _is_framed_string(v):
                raise FramingError(f"argument '{k}' is not framed user data")
