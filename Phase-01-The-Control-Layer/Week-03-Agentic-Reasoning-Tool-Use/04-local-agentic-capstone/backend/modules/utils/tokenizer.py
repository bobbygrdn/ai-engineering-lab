"""Token counting helper with optional tiktoken support.

Falls back to a word-based estimate when `tiktoken` is unavailable.
"""
from typing import Optional

try:
    import tiktoken
except Exception:
    tiktoken = None


def count_tokens(text: str, model: Optional[str] = None) -> int:
    if not text:
        return 0
    if tiktoken is not None:
        try:
            # default to cl100k_base if unknown
            enc = tiktoken.encoding_for_model(model) if model else tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            pass
    # fallback: rough word count
    return max(1, len(text.split()))


__all__ = ["count_tokens"]
