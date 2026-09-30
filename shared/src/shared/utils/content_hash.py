import hashlib
from typing import List


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_texts(texts: List[str]) -> str:
    """Order matters. Each text is hashed first, so ["ab", "c"] and ["a", "bc"] differ."""
    return content_hash("\n".join(content_hash(text) for text in texts))
