try:
    import tiktoken
    _ENCODER = tiktoken.get_encoding("cl100k_base")
except ImportError:
    _ENCODER = None


def count_tokens(text: str) -> int:
    """Counts the number of tokens in a given text."""
    if _ENCODER:
        return len(_ENCODER.encode(text))
    return max(1, len(text) // 4) 

def tokens_for_chunks(chunks):
    """Counts the number of tokens for each chunk in a list of chunks."""
    return [count_tokens(c["text"]) for c in chunks]