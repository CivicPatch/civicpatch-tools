"""One field of one matched person, graded at one level, with the normalised values the page
colours by, so its colours agree with the grade."""

from typing import Callable

from shared.utils.email_utils import normalize_email
from shared.utils.label_parser import parse_label
from shared.utils.phone_utils import normalize_phone_number
from shared.utils.taxonomy import Taxonomy
from shared.utils.url_utils import canonical_url

from schemas.roster_comparisons import FieldComparison, FieldLevel


def grade(uploaded: set[str], civicpatch: set[str]) -> FieldLevel:
    if not uploaded and not civicpatch:
        return FieldLevel.BOTH_EMPTY
    if not uploaded:
        return FieldLevel.UPLOADED_DATA_HAS_NONE
    if not civicpatch:
        return FieldLevel.CIVICPATCH_HAS_NONE
    if uploaded == civicpatch:
        return FieldLevel.EQUAL
    if uploaded < civicpatch:
        return FieldLevel.CIVICPATCH_HAS_MORE
    if uploaded > civicpatch:
        return FieldLevel.UPLOADED_DATA_HAS_MORE
    if uploaded & civicpatch:
        return FieldLevel.OVERLAP
    return FieldLevel.DIFFERS


def compare_emails(uploaded: list[str], civicpatch: list[str]) -> FieldComparison:
    return _compare(uploaded, civicpatch, _email)


def compare_phones(uploaded: list[str], civicpatch: list[str]) -> FieldComparison:
    return _compare(uploaded, civicpatch, _phone)


def compare_urls(uploaded: list[str], civicpatch: list[str]) -> FieldComparison:
    return _compare(uploaded, civicpatch, canonical_url)


def compare_start_date(uploaded: str | None, civicpatch: str | None) -> FieldComparison:
    return _compare(_present(uploaded), _present(civicpatch), str.strip)


def compare_role(
    uploaded: str | None, civicpatch_role_ids: list[str], taxonomy: Taxonomy
) -> FieldComparison:
    """By role id, the uploaded text parsed with the taxonomy ("Councilmember" is Council Member)."""
    labels_by_id = {role_id: label for label, role_id in taxonomy.role_ids.items()}
    civicpatch_labels = [labels_by_id.get(role_id, role_id) for role_id in civicpatch_role_ids]
    text = (uploaded or "").strip()
    uploaded_ids = role_ids(text, taxonomy)
    if role_not_recognised(text, taxonomy):
        return FieldComparison(
            level=FieldLevel.UNKNOWN, uploaded=[text], civicpatch=civicpatch_labels
        )
    return FieldComparison(
        level=grade(set(uploaded_ids), set(civicpatch_role_ids)),
        uploaded=[labels_by_id[role_id] for role_id in uploaded_ids],
        civicpatch=civicpatch_labels,
    )


def role_not_recognised(text: str | None, taxonomy: Taxonomy) -> bool:
    """Role text was given, and names no role the taxonomy knows."""
    stripped = (text or "").strip()
    return bool(stripped) and not role_ids(stripped, taxonomy)


def role_ids(text: str, taxonomy: Taxonomy) -> list[str]:
    """The ids of the roles a text names; empty when it names none the taxonomy knows."""
    if not text:
        return []
    parsed = parse_label(text, taxonomy)
    return [taxonomy.role_ids[label] for label in parsed.roles if label in taxonomy.role_ids]


def _compare(
    uploaded: list[str], civicpatch: list[str], normalise: Callable[[str], str]
) -> FieldComparison:
    uploaded_values = _normalised(uploaded, normalise)
    civicpatch_values = _normalised(civicpatch, normalise)
    return FieldComparison(
        level=grade(set(uploaded_values), set(civicpatch_values)),
        uploaded=uploaded_values,
        civicpatch=civicpatch_values,
    )


def _normalised(values: list[str], normalise: Callable[[str], str]) -> list[str]:
    """In the order given, without blanks or repeats."""
    return list(dict.fromkeys(normalise(value) for value in values if value and value.strip()))


def _email(value: str) -> str:
    return normalize_email(value) or value.strip()


def _phone(value: str) -> str:
    # A number that doesn't parse stays as written: it then differs, rather than vanishing.
    return normalize_phone_number(value) or value.strip()


def _present(value: str | None) -> list[str]:
    return [value] if value else []
