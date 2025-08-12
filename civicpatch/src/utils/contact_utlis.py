def format_phone_number(phone_number: str) -> str:
    """
    Format a phone number to a standard format.
    """
    if not phone_number:
        return ""
    # Remove non-numeric characters
    digits = ''.join(filter(str.isdigit, phone_number))
    if len(digits) == 10:  # Standard US phone number
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return digits  # Return as is if not standard length