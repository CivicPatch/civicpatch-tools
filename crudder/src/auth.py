import hmac
import hashlib

def hash_string(string: str, hash_key: str) -> str:
    """Hash an API key using HMAC-SHA256 and the database hash key."""
    return hmac.new(
        hash_key.encode(),
        string.encode(),
        hashlib.sha256
    ).hexdigest()