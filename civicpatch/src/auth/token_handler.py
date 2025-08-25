from fastapi import Request
import hashlib
import hmac

def generate_github_action_data_query_token(secret: str, timestamp: str, body: str) -> str:
    """
    Generates a token for GitHub Action data query.
    This is a placeholder function and should be replaced with actual token generation logic.
    """
    signature = hmac.new(
        secret.encode(), (timestamp + body).encode(), hashlib.sha256
    ).hexdigest()

    return signature

def verify_github_action_data_query(
    secret: str,
    timestamp: str,
    signature: str,
    body: str = "",
) -> bool:
    expected_signature = generate_github_action_data_query_token(secret, timestamp, body)
    return hmac.compare_digest(expected_signature, signature)

   