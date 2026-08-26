"""The people a scrape's sightings imply. `post_derivation` is the same step for posts.

Pure over records, identities and a taxonomy, bar the log it writes to.

`identities` decides which names are one person: cp.org's own published people where it has
them, else what the scrape's research step turned up.
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from shared.schemas import Person, PersonRecord
from shared.utils import email_utils, name_utils, phone_utils, url_utils
from shared.utils.label_parser import parse_label
from shared.utils.log_protocol import Log
from shared.utils.taxonomy import Taxonomy


def merge_labels(records: List[PersonRecord], taxonomy: Taxonomy) -> List[str]:
    """One label per distinct statement, not per distinct spelling.

    Deduped on the parse, not the string. Three Seattle pages call one person "Councilmember
    Position 8", "Council Member Position 8" and "Council Member Position 8 (Citywide, …)";
    the first two parse identically, so keeping both is noise that reads as two offices.

    A label whose parse differs at all survives — the third above keeps its residue — so this
    only ever collapses labels that say the same thing.
    """
    kept: dict[tuple, str] = {}
    for label in sorted({record.label for record in records if record.label}):
        parsed = parse_label(label, taxonomy)
        key = (
            parsed.role,
            str(parsed.division),
            tuple(parsed.other_designations),
            tuple(parsed.unmatched),
        )
        kept.setdefault(key, label)
    return list(kept.values())


def merge_field(values: List[str]) -> str:
    """Most frequent non-empty value; a tie breaks alphabetically."""
    value_counter = Counter(value for value in values if value)
    if not value_counter:
        return ""
    max_count = max(value_counter.values())
    return sorted(value for value, count in value_counter.items() if count == max_count)[0]


def merge_field_to_list(values: List[str]) -> List[str]:
    """Unique non-empty values."""
    return sorted({value for value in values if value})


def normalize_record(log: Log, record: PersonRecord) -> PersonRecord:
    normalized_phone = (
        phone_utils.normalize_phone_number(record.phone) if record.phone else None
    )
    if record.phone and normalized_phone is None:
        log.warning(f"Failed to parse phone number: {record.phone}")

    normalized_email = email_utils.normalize_email(record.email)
    if normalized_email and not email_utils.is_valid_email(normalized_email):
        log.warning(f"Invalid email address found: {record.email}")
        if not record.url and url_utils.is_valid_url(normalized_email):
            record.url = url_utils.format_url(normalized_email)
        normalized_email = None

    return PersonRecord(
        name=record.name,
        # Verbatim: normalizing here is what 2.2 removed — cp.org parses.
        label=record.label,
        phone=normalized_phone,
        email=normalized_email,
        url=record.url,
        start_date=record.start_date,
        end_date=record.end_date,
        image=record.image,
        source_url=record.source_url,
    )


def merge_weak_tie_groups(
    groups: Dict[str, List[PersonRecord]],
    taxonomy: Taxonomy,
) -> Dict[str, List[PersonRecord]]:
    """Fold a last-name-only group into a full-name one sharing that surname and an office."""

    def is_last_name_only(name: str) -> bool:
        return len(name.split()) == 1

    def parsed_last_name(name: str) -> str:
        parsed = name_utils.parse_name(name)
        return parsed.last.lower() if parsed.last else name.split()[-1].lower()

    def office_keys(records: List[PersonRecord]) -> set:
        """(role, division, designations) per record. Parsed, not compared raw, so two
        spellings of one office still match; the parse is discarded after the merge."""
        result = set()
        for r in records:
            parsed = parse_label(r.label, taxonomy)
            division = parsed.division.value if parsed.division else ""
            result.add((parsed.role or "", division, tuple(parsed.other_designations)))
        return result

    weak_keys = [k for k in groups if is_last_name_only(k)]
    result: Dict[str, List[PersonRecord]] = dict(groups)

    for wk in weak_keys:
        if wk not in result:
            continue
        weak_office_keys = office_keys(result[wk])
        if not weak_office_keys:
            continue
        for sk in list(result):
            if sk == wk or is_last_name_only(sk):
                continue
            if parsed_last_name(sk) != wk.lower():
                continue
            if not weak_office_keys & office_keys(result[sk]):
                continue
            result[sk] = result[sk] + result[wk]
            del result[wk]
            break

    return result


def get_source_urls(person_records: List[PersonRecord]) -> List[str]:
    """Every page the person was seen on — a sighting exists because that page named them."""
    return sorted({record.source_url for record in person_records if record.source_url})


def canonical_name(published_name: str, records: List[PersonRecord]) -> str:
    """Which of a person's spellings becomes their name.

    A name we already know them by wins outright: that is a human's answer, and a scrape must
    not rename someone because one page spelled them differently. Otherwise the most frequent
    spelling, merged like any other field.

    The name is the only merged field that has to pick a winner — every other one is a union,
    where nothing loses.

    `known_name` is empty when nobody has published this person. At ingest that is decided by
    `identities`; at read time by whether the resolved id is in `people`.
    """
    return published_name or merge_field([record.name for record in records])


def merge_records_to_person(
    log: Log,
    canonical_name: str,
    records: List[PersonRecord],
    jurisdiction_ocdid: str,
    taxonomy: Taxonomy,
) -> Person:
    records = [normalize_record(log, r) for r in records]

    image = merge_field([r.image for r in records if r.image is not None])
    merged_labels = merge_labels(records, taxonomy)
    phones = merge_field_to_list([r.phone for r in records if r.phone is not None])
    emails = merge_field_to_list([r.email for r in records if r.email is not None])
    urls = merge_field_to_list([r.url for r in records if r.url is not None])
    start_date = merge_field(
        [r.start_date for r in records if r.start_date is not None]
    )
    end_date = merge_field([r.end_date for r in records if r.end_date is not None])

    other_names = sorted(
        {
            person.name
            for person in records
            if person.name and person.name != canonical_name
        }
    )

    person = Person(
        name=canonical_name,
        other_names=other_names,
        labels=merged_labels,
        phones=phones,
        emails=emails,
        urls=urls,
        start_date=start_date,
        end_date=end_date,
        image=image,
        cdn_image="",
        jurisdiction_ocdid=jurisdiction_ocdid,
        source_urls=[],
        updated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    person.source_urls = get_source_urls(records)
    return person


def derived_people(
    records: List[PersonRecord],
    identities: Dict[str, List[str]],
    taxonomy: Taxonomy,
    jurisdiction_ocdid: str,
    log: Log,
) -> List[Tuple[Person, List[PersonRecord]]]:
    """Group a scrape's sightings into people, each with the records behind it.

    Everyone seen comes back: scope lives on the post, as `posts._is_tracked`, not on whether
    a label resolved.
    """
    canonical_map = name_utils.build_canonical_map(
        [{"name": r.name} for r in records], identities
    )

    groups: Dict[str, List[PersonRecord]] = defaultdict(list)
    for record in records:
        groups[canonical_map.get(record.name, record.name)].append(record)

    groups = merge_weak_tie_groups(groups, taxonomy)

    return [
        (
            merge_records_to_person(
                log,
                canonical_name(group_name if group_name in identities else "", group)
                or group_name,
                group,
                jurisdiction_ocdid,
                taxonomy,
            ),
            group,
        )
        for group_name, group in groups.items()
    ]
