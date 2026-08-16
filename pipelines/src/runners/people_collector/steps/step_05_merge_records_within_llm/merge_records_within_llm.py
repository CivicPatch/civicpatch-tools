from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List

import runners.people_collector.steps.step_05_merge_records_within_llm.field_mergers as field_mergers
from runners.people_collector.schemas import (
    LLMPersonRecord,
    MergeRecordsWithinLLMStep,
    PeopleCollectorContext,
    Person,
    UnrecognizedRole,
)
from runners.people_collector.steps.step_05_merge_records_within_llm.normalize import (
    normalize_record,
)
from shared.utils import name_utils
from utils import log_utils
from shared.utils.label_parser import parse_label
from shared.utils.taxonomy import Taxonomy, build_taxonomy


def merge_records_within_llm(
    context: PeopleCollectorContext,
) -> MergeRecordsWithinLLMStep:
    """
    Consolidate records to produce a unified list of Person objects.
    """
    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    assert context.data.process_page_content_step is not None, (
        "should never happen — process_page_content_step is required before merge_records_within_llm"
    )

    assert context.data.research_municipality_step is not None, (
        "should never happen — research_municipality_step is required before merge_records_within_llm"
    )

    taxonomy = build_taxonomy(context.data.role_config)

    records = context.data.process_page_content_step.records
    all_records = [record for group in records.values() for record in group]
    logger = log_utils.get_pipeline_run_logger(jurisdiction_ocdid)

    identities = context.data.research_municipality_step.identities

    all_unrecognized: List[UnrecognizedRole] = []
    all_excluded: List[Person] = []

    # Use name_utils to map every record's name to a canonical name
    canonical_map = name_utils.build_canonical_map(
        [{"name": r.name} for r in all_records], identities
    )

    # Group records by canonical name
    groups: Dict[str, List[LLMPersonRecord]] = defaultdict(list)
    for record in all_records:
        groups[canonical_map.get(record.name, record.name)].append(record)

    groups = merge_weak_tie_groups_within_llm(groups, taxonomy)

    # Merge each group into a Person
    kept_people: List[Person] = []
    for canonical_name, group in groups.items():
        raw_labels = list({record.label for record in group if record.label})
        merged_person = merge_llm_people_to_person(
            logger, taxonomy, canonical_name, group, jurisdiction_ocdid
        )

        if raw_labels and not any(
            parse_label(label, taxonomy).role for label in merged_person.labels
        ):
            logger.info(
                f"Excluded person: {canonical_name} — no known role in {raw_labels}"
            )
            all_excluded.append(merged_person)
        else:
            kept_people.append(merged_person)

    # over both lists — an excluded person's label is what triage needs to see
    for person in kept_people + all_excluded:
        for label in person.labels:
            if not parse_label(label, taxonomy).role:
                all_unrecognized.append(
                    UnrecognizedRole(role=label, person_name=person.name)
                )

    return MergeRecordsWithinLLMStep(
        records=kept_people,
        unrecognized_roles=all_unrecognized,
        excluded_people=all_excluded,
    )


def merge_weak_tie_groups_within_llm(
    groups: Dict[str, List[LLMPersonRecord]],
    taxonomy: Taxonomy,
) -> Dict[str, List[LLMPersonRecord]]:
    """
    Merge last-name-only canonical groups into full-name groups when they share
    the same last name and at least one office.
    """

    def is_last_name_only(name: str) -> bool:
        return len(name.split()) == 1

    def parsed_last_name(name: str) -> str:
        parsed = name_utils.parse_name(name)
        return parsed.last.lower() if parsed.last else name.split()[-1].lower()

    def office_keys(records: List[LLMPersonRecord]) -> set:
        """(role, area, designations) per record. Parsed, not compared raw, so two
        spellings of one office still match; the parse is discarded after the merge."""
        result = set()
        for r in records:
            parsed = parse_label(r.label, taxonomy)
            area = parsed.division.value if parsed.division else ""
            result.add((parsed.role or "", area, tuple(parsed.seats)))
        return result

    weak_keys = [k for k in groups if is_last_name_only(k)]
    result: Dict[str, List[LLMPersonRecord]] = dict(groups)

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


def get_source_urls(person_records: list[LLMPersonRecord], person: Person) -> list:
    """
    For each unique value in the merged fields, include the source_url of the record that contributed it.
    Only one source_url per unique value, tiebreaking by first record.
    """
    field_map = [
        ("labels", "label"),
        # ('divisions', 'divisions'),
        ("phones", "phone"),
        ("emails", "email"),
        # ('urls', 'url'),
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


def merge_llm_people_to_person(
    logger: log_utils.PipelineRunLogger,
    taxonomy: Taxonomy,
    canonical_name: str,
    records: List[LLMPersonRecord],
    jurisdiction_ocdid: str,
) -> Person:
    """
    Merge a list of LLMPersonRecord objects into a single Person object.
    """
    # Normalize records
    records = [normalize_record(logger, r) for r in records]

    # Use helper functions to merge fields
    image = field_mergers.merge_field([r.image for r in records if r.image is not None])
    merged_labels = field_mergers.merge_labels(records)
    phones = field_mergers.merge_field_to_list(
        [r.phone for r in records if r.phone is not None]
    )
    emails = field_mergers.merge_field_to_list(
        [r.email for r in records if r.email is not None]
    )
    urls = field_mergers.merge_field_to_list(
        [r.url for r in records if r.url is not None]
    )
    start_date = field_mergers.merge_field(
        [r.start_date for r in records if r.start_date is not None]
    )
    end_date = field_mergers.merge_field(
        [r.end_date for r in records if r.end_date is not None]
    )

    # Collect all unique names from the group, excluding the canonical name
    other_names = list(
        set(
            person.name
            for person in records
            if person.name and person.name != canonical_name
        )
    )

    person = Person(
        name=canonical_name,
        other_names=other_names,  # Add other names here
        labels=merged_labels,
        phones=phones,
        emails=emails,
        urls=urls,
        start_date=start_date,
        end_date=end_date,
        image=image,
        cdn_image="",  # Placeholder for CDN image
        jurisdiction_ocdid=jurisdiction_ocdid,
        source_urls=[],
        updated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    person.source_urls = get_source_urls(records, person)
    return person
