from typing import List
from modules.utils.tokenizer import count_tokens


def summarize_messages(messages: List[object], max_words: int = 120) -> tuple[str, int]:
    """Create a lightweight extractive summary from a list of StoredMessage.

    Returns (summary_text, estimated_token_count).
    """
    if not messages:
        return "", 0
    # take the last N messages' content and produce a short joined summary
    contents = []
    for m in messages[-8:]:
        # messages may be StoredMessage or similar with .message.role and .message.content
        try:
            role = getattr(m.message, "role", "")
            content = getattr(m.message, "content", "")
        except Exception:
            role = getattr(m, "role", "")
            content = getattr(m, "content", "")
        contents.append(f"{str(role).title()}: {content}")
    joined = " \n ".join(contents)
    words = joined.split()
    if len(words) > max_words:
        joined = "..." + " ".join(words[-max_words:])
    estimated_tokens = count_tokens(joined)
    summary_text = "Summary of earlier conversation: " + joined
    return summary_text, estimated_tokens


__all__ = ["summarize_messages"]
