import hashlib
import uuid

def generate_id(text: str) -> str:
    """
    Generates a unique ID for the given text using SHA-256 hashing converts the hash
    to a valid UUID format.
    """
    # SHA‑256 → first 128 bits → UUID
    digest = hashlib.sha256(text.encode("utf‑8")).digest()[:16]
    return str(uuid.UUID(bytes=digest))