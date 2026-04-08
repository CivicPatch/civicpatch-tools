
import hashlib
import hmac

def hash_string(string: str, hash_key: str) -> str:
    return hmac.new(hash_key.encode(), string.encode(), hashlib.sha512).hexdigest()