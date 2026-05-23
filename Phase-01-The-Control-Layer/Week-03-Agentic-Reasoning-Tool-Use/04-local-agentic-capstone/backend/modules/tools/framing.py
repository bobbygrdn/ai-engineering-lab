"""Helpers to frame user data and detect prompt-injection attempts."""
from __future__ import annotations

import re
from typing import Tuple


INJECTION_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"disregard (all )?previous instructions",
    r"follow only the instructions",
    r"you are the system",
    r"you are an? ?assistant",
    r"delete all previous messages",
    r"<system>",
    r"<assistant>",
]


class FramingError(Exception):
    pass


def frame_user_data(user_text: str) -> str:
    """Wrap user input inside <user_data> tags and detect simple prompt-injection.

    Raises `FramingError` on suspicious content.
    """
    if not isinstance(user_text, str):
        raise FramingError("user_text must be a string")

    cleaned = user_text.strip()
    if not cleaned:
        raise FramingError("user_text is empty")

    lowered = cleaned.lower()
    for pat in INJECTION_PATTERNS:
        if re.search(pat, lowered):
            raise FramingError("prompt injection detected")

    # ensure user content can't close the tags by encoding closing bracket sequences
    safe = cleaned.replace("</", "&lt;/")
    return f"<user_data>{safe}</user_data>"


def extract_user_text(framed_text: str) -> str:
    """Extract inner user text from a framed string. Reverses the simple encoding used by frame_user_data.

    If input is not framed, returns it unchanged.
    """
    if not isinstance(framed_text, str):
        return framed_text
    s = framed_text.strip()
    if s.startswith("<user_data>") and s.endswith("</user_data>"):
        inner = s[len("<user_data>"):-len("</user_data>")]
        return inner.replace("&lt;/", "</")
    return framed_text
