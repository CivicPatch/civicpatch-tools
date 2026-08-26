"""Phone numbers as US national format, or nothing.

Pure and total: every input returns a string or `None`, and nothing raises. That is
deliberate. These are the check the pipeline runs before accepting an extraction, and a
check that signals failure two ways — `None` for an invalid number, an exception for an
unparseable one — gets read as one way by its callers. It was: the retry guard in
`heuristics.py` wrapped only the exception, so `555-555-5555` passed and `not a phone`
did not.

Normalizing is not storing. The pipeline calls these to decide whether to re-read a page;
the raw string is what goes into `source_records`, because evidence is what the page said.
The canonical value belongs to the derivation, and is applied where one is written.
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
