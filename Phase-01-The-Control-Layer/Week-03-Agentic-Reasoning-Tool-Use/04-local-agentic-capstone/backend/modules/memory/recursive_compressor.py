from typing import List, Tuple
from modules.memory.summarizer import summarize_messages
from modules.utils.interactions import record_event


def recursive_compress(stored_messages: List[object], token_budget: int, max_iterations: int = 8) -> Tuple[List[object], int]:
    """Recursively compress earliest non-system messages until the token budget is met or
    no further compression gains are possible.

    - stored_messages: list of objects with attributes `message.role`, `message.content`, and `token_count`.
    - token_budget: desired total token budget to achieve
    Returns: (new_messages, new_total_tokens)
    """
    if not stored_messages:
        return stored_messages, 0

    # compute helper to get non-system messages
    def non_system_list(msgs):
        return [m for m in msgs if getattr(m.message, "role", getattr(m, "role", "")) != "system"]

    total_tokens = sum(getattr(m, "token_count", 0) for m in stored_messages)
    if total_tokens <= token_budget:
        return stored_messages, total_tokens

    try:
        record_event("recursive_compress_started", {"current_tokens": total_tokens, "budget": token_budget})
    except Exception:
        pass

    messages = list(stored_messages)

    for _ in range(max_iterations):
        total_tokens = sum(getattr(m, "token_count", 0) for m in messages)
        if total_tokens <= token_budget:
            break

        non_system = non_system_list(messages)
        if len(non_system) <= 1:
            # nothing sensible to compress further
            break

        # choose earliest half of non-system messages to compress (preserve recency)
        cutoff = max(1, len(non_system) // 2)
        to_summarize = non_system[:cutoff]

        # calculate token counts of the range to be removed
        removed_tokens = sum(getattr(m, "token_count", 0) for m in to_summarize)

        # produce a summary for those messages
        summary_text, summary_tokens = summarize_messages(to_summarize)

        try:
            record_event("recursive_compress_iteration", {"iteration": _, "removed_tokens": removed_tokens, "summary_tokens": summary_tokens})
        except Exception:
            pass

        # if summary is not smaller than the removed chunk, avoid replacing (no gain)
        if summary_tokens >= removed_tokens:
            # If no compression gain, stop iteration
            break

        # Remove the to_summarize messages from the main list while preserving order
        new_msgs = []
        removed = 0
        for m in messages:
            if removed < cutoff and getattr(m.message, "role", getattr(m, "role", "")) != "system" and m in to_summarize:
                removed += 1
                continue
            new_msgs.append(m)

        # insert the summary as an assistant message at the front of the remaining list
        # Avoid importing working_memory here to prevent circular imports; create a small
        # lightweight stored-like object that provides the expected attributes.
        from types import SimpleNamespace

        summary_msg = SimpleNamespace(role="assistant", content=summary_text)
        summary_stored = SimpleNamespace(message=summary_msg, token_count=summary_tokens)
        # mark this stored summary so trimming logic can avoid evicting it immediately
        try:
            setattr(summary_stored, "_is_summary", True)
        except Exception:
            pass

        # insert the summary near the beginning so older context is still earlier than recents
        new_msgs.insert(0, summary_stored)

        messages = new_msgs
        try:
            record_event("recursive_compress_inserted_summary", {"summary_tokens": summary_tokens, "removed_tokens": removed_tokens})
        except Exception:
            pass

    total_tokens = sum(getattr(m, "token_count", 0) for m in messages)
    try:
        record_event("recursive_compress_completed", {"final_tokens": total_tokens, "budget": token_budget})
    except Exception:
        pass
    return messages, total_tokens


__all__ = ["recursive_compress"]
