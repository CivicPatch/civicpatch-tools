import re

def is_valid_email(email):
    """
    Validates an email address using a simple regex pattern.
    Note: This is a basic validation and may not cover all valid email formats.
    """
    email_pattern = r"^[^@]+@[^@]+$" 
    return re.match(email_pattern, email) is not None

def normalize_email(email):
    """
    Normalizes an email address by stripping whitespace and converting to lowercase.
    """
    if not email:
        return None
    return re.sub(r"\s+", "", email).lower()