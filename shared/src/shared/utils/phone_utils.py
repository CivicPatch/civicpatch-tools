import phonenumbers
from typing import Optional


def normalize_phone_number(phone: str) -> Optional[str]:
    """
    Normalizes a phone number to a standard format.
    """
    if not phone:
        return ""
    try:
        parsed = phonenumbers.parse(phone, "US")
        if not phonenumbers.is_valid_number(parsed):
            return None  # Return None if not valid
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
    except phonenumbers.NumberParseException as e:
        raise ValueError(f"Could not parse phone number: {phone!r}") from e


def normalize_first_phone(phone: str) -> Optional[str]:
    if not phone:
        return None
    try:
        return normalize_phone_number(phone)
    except ValueError:
        pass
    for match in phonenumbers.PhoneNumberMatcher(phone, "US"):
        return phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.NATIONAL)
    return None
