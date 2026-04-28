import re
from typing import List
from runners.people_collector.schemas import LLMPerson
from shared.utils import phone_utils, email_utils, url_utils, name_utils


def check_page_heuristics(logger, source_url: str, input_text: str, records_found: List[LLMPerson]) -> bool:
    """
    Per-page heuristics check for a single LLM's results.
    Returns True if every non-empty field (email, phone, url, role) in each LLMPerson
    is present in the input_text.
    """
    input_text_lower = input_text.lower()
    for person in records_found:
        if person.name and not _name_in_text(person.name, input_text_lower):
            logger.warning(f"Name not found in input text: {person.name} under source url: {source_url}")
            return False
        if person.email and not _email_in_text(person.email, input_text_lower):
            logger.warning(f"Email not found in input text: {person.email} under source url: {source_url}")
            return False
        if person.phone:
            if not _phone_in_text(person.phone, input_text):
                logger.warning(f"Phone not found in input text: {person.phone} under source url: {source_url}")
                return False
            try:
                phone_utils.normalize_phone_number(person.phone)
            except ValueError:
                if phone_utils.normalize_first_phone(person.phone) is None:
                    logger.warning(f"Phone not normalizable, forcing retry: {person.phone} under source url: {source_url}")
                    return False
        if person.url and not url_utils.url_in_text(person.url, input_text):
            if not url_utils.same_url(person.url, source_url):
                logger.warning(f"URL not found in input text: {person.url} under source url: {source_url}")
                return False

        # TODO: Need to use a free model/spacy to do fuzzy matching on roles and dates
        # As needed
    return True


def _name_in_text(name: str, text_lower: str) -> bool:
    """
    Check if a name appears in text, allowing for minor formatting differences
    (e.g., "Martin Cantu Jr." vs "Martin Cantu, Jr.").
    """
    name_norm = name_utils.normalize_text_for_search(name)
    text_norm = name_utils.normalize_text_for_search(text_lower)

    if name_norm in text_norm:
        return True

    # Handle line-break artifacts where a name is split mid-word across lines
    if re.sub(r"\s+", "", name_norm) in re.sub(r"\s+", "", text_norm):
        return True

    parsed = name_utils.parse_name(name)
    parts = [name_utils.normalize_text_for_search(p) for p in [parsed.first, parsed.last] if p]
    return bool(parts) and all(part in text_norm for part in parts)


def _email_in_text(email: str, text_lower: str) -> bool:
    normalized = email_utils.normalize_email(email)
    if not normalized or "@" not in normalized:
        return False
    if normalized in text_lower:
        return True
    # Strip whitespace, unescape \_, and remove all non-email characters so markdown link syntax
    # and broken mailto hrefs (e.g. [user@domain.tx](mailto:user@domain.tx) .us) collapse together
    text_clean = re.sub(r"[^a-z0-9@._+\-]", "", text_lower.replace("\\_", "_"))
    if normalized in text_clean:
        return True
    # Last resort: strip all separators from both sides so district1@ci.lamesa.tx.us
    # matches district1cilamaesatxus in text
    email_alnum = re.sub(r"[^a-z0-9]", "", normalized)
    text_alnum = re.sub(r"[^a-z0-9]", "", text_clean)
    return bool(email_alnum) and email_alnum in text_alnum


def _normalize_phone(phone: str) -> str:
    """Strip all non-digit characters."""
    return re.sub(r'\D', '', phone)


def _phone_in_text(phone: str, input_text: str) -> bool:
    """Check if the core digits of a phone number appear in the text."""
    normalized_phone = _normalize_phone(phone)
    if not normalized_phone:
        return False
    normalized_text = _normalize_phone(input_text)
    return normalized_phone in normalized_text
