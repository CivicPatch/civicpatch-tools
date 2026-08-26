"""Phone numbers as US national format, or nothing.

Total on purpose: a string or `None`, never an exception. Signalling failure two ways got read
as one — the retry guard wrapped only the exception, so `555-555-5555` passed.

The pipeline calls these to decide whether to re-read a page; `source_records` keeps the raw
string either way.
"""

from typing import Optional

import phonenumbers


def normalize_phone_number(phone: Optional[str]) -> Optional[str]:
    """US national format — `(856) 358-2509` — or None if this is not a valid number."""
    if not phone:
        return None
    try:
        parsed = phonenumbers.parse(phone, "US")
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
