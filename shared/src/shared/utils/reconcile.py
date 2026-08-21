"""Grouping a scrape's sightings into people.

Moved out of the pipeline's step 05 on 2026-08-21. It lives here because it is changing hands:
the pipeline does this today, cp.org does it once records cross the boundary instead of merged
people, and both need it while that transition runs.

Pure over records, identities and a taxonomy. Logging is a `Protocol` so `shared` need not
depend on `pipelines` — the dependency only runs the other way.

`identities` decides which names are one person. It comes from the pipeline's research step
today, built either from an LLM guess or from cp.org's own published people. That circularity
gets *shorter* once cp.org reconciles, since it already holds what it would compare against.
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Protocol, Tuple

from shared.schemas import Person, PersonRecord
from shared.utils import email_utils, name_utils, phone_utils, url_utils
from shared.utils.label_parser import parse_label
from shared.utils.taxonomy import Taxonomy


class ReconcileLog(Protocol):
    def debug(self, message: str) -> None: ...
    def info(self, message: str) -> None: ...
    def warning(self, message: str) -> None: ...


def merge_labels(records: List[PersonRecord]) -> List[str]:
    """Unique raw labels across records — one per office the person was seen holding."""
    unique_labels = set()
    for record in records:
        if record.label:
            unique_labels.add(record.label)
    return list(unique_labels)


def merge_field(values: List[str]) -> str:
    """Most frequent non-empty value; a tie breaks on first-seen."""
    value_counter = Counter(value for value in values if value)
    if not value_counter:
        return ""
    most_common = value_counter.most_common()
    max_count = most_common[0][1]
    tied_values = [value for value, count in most_common if count == max_count]
    return tied_values[0]


def merge_field_to_list(values: List[str]) -> List[str]:
    """Unique non-empty values."""
    return list(set(value for value in values if value))


def normalize_record(log: ReconcileLog, record: PersonRecord) -> PersonRecord:
    normalized_phone = (
        phone_utils.normalize_first_phone(record.phone) if record.phone else None
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
        """(role, area, designations) per record. Parsed, not compared raw, so two
        spellings of one office still match; the parse is discarded after the merge."""
        result = set()
        for r in records:
            parsed = parse_label(r.label, taxonomy)
            area = parsed.division.value if parsed.division else ""
            result.add((parsed.role or "", area, tuple(parsed.other_designations)))
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


def get_source_urls(person_records: list[PersonRecord], person: Person) -> list:
    """The url of the first record contributing each merged value."""
    field_map = [
        ("labels", "label"),
        ("phones", "phone"),
        ("emails", "email"),
    ]
    merged_values = {plural: set(getattr(person, plural)) for plural, _ in field_map}
    source_urls = set()

    for plural, singular in field_map:
        for value in merged_values[plural]:
            for record in person_records:
                record_values = getattr(record, singular)
                values = (
                    set(record_values)
                    if isinstance(record_values, list)
                    else {record_values}
                )
                if value in values:
                    url = getattr(record, "source_url", None)
                    if url:
                        source_urls.add(url)
                    break  # Tiebreak: only the first record that contributed this value

    return list(source_urls)


def merge_records_to_person(
    log: ReconcileLog,
    canonical_name: str,
    records: List[PersonRecord],
    jurisdiction_ocdid: str,
) -> Person:
    records = [normalize_record(log, r) for r in records]

    image = merge_field([r.image for r in records if r.image is not None])
    merged_labels = merge_labels(records)
    phones = merge_field_to_list([r.phone for r in records if r.phone is not None])
    emails = merge_field_to_list([r.email for r in records if r.email is not None])
    urls = merge_field_to_list([r.url for r in records if r.url is not None])
    start_date = merge_field(
        [r.start_date for r in records if r.start_date is not None]
    )
    end_date = merge_field([r.end_date for r in records if r.end_date is not None])

    other_names = list(
        set(
            person.name
            for person in records
            if person.name and person.name != canonical_name
        )
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

    person.source_urls = get_source_urls(records, person)
    return person


def reconcile(
    records: List[PersonRecord],
    identities: Dict[str, List[str]],
    taxonomy: Taxonomy,
    jurisdiction_ocdid: str,
    log: ReconcileLog,
) -> Tuple[List[Person], List[Person]]:
    """Group a scrape's sightings into people. Returns (kept, excluded).

    Excluded means no label resolved to a known role — the person was seen, but nothing in the
    taxonomy claims what they are. Kept separate rather than dropped so triage can see them.
    """
    canonical_map = name_utils.build_canonical_map(
        [{"name": r.name} for r in records], identities
    )

    groups: Dict[str, List[PersonRecord]] = defaultdict(list)
    for record in records:
        groups[canonical_map.get(record.name, record.name)].append(record)

    groups = merge_weak_tie_groups(groups, taxonomy)

    kept: List[Person] = []
    excluded: List[Person] = []
    for canonical_name, group in groups.items():
        raw_labels = list({record.label for record in group if record.label})
        person = merge_records_to_person(log, canonical_name, group, jurisdiction_ocdid)
        if raw_labels and not any(
            parse_label(label, taxonomy).role for label in person.labels
        ):
            log.info(f"Excluded {canonical_name}: no known role in {raw_labels}")
            excluded.append(person)
        else:
            kept.append(person)

    return kept, excluded
