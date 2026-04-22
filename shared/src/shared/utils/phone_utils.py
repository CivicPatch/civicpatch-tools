import phonenumbers

def normalize_phone_number(phone: str) -> str:
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
