from typing import List, Dict, Tuple
from utils import people_utils
from shared.utils import name_utils
from domain.models import Person
from jobs.people_collector.schemas import (
    PeopleCollectorContext,
    MergeRecordsAcrossLLMsStep,
)
from collections import Counter
from datetime import datetime, timezone
import jobs.people_collector.steps.step_07_merge_records_across_llms.field_mergers as field_mergers
import jobs.people_collector.steps.step_07_merge_records_across_llms.record_comparison as record_comparison

MINIMUM_AGREEMENT_SCORE = 80
FIELD_WEIGHTS = {
    "roles": 1.0,
    "designations": 0.8,
    "emails": 0.5,
    "urls": 0.2,
    "phones": 0.2,
    "start_date": 0.5,
    "end_date": 0.5,
}
FIELDS_TO_CHECK = list(FIELD_WEIGHTS.keys())

# TODO: move disagreements logic to open-data, should not live here

# --- Types ---

PersonWithSource = Tuple[Person, str]
GroupByLLM = Dict[str, List[Person]]


# --- Main entry point ---

def merge_records_across_llms(context: PeopleCollectorContext) -> MergeRecordsAcrossLLMsStep:
    """Merge records across all LLMs to produce a unified list of Person objects."""
    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    people_by_llm: Dict[str, List[Person]] = context.data.merge_records_within_llm_step.people_by_llm
    identity_names = _resolve_identity_names(context)

    groups = group_records_across_llms(identity_names, people_by_llm)
    merged_people, all_disagreements = _merge_groups(groups, jurisdiction_ocdid, people_by_llm)

    overall_agreement_score = record_comparison.calculate_overall_agreement_score(
        FIELD_WEIGHTS, FIELDS_TO_CHECK, all_disagreements, len(people_by_llm),
    )

    return MergeRecordsAcrossLLMsStep(
        people=people_utils.sort_people(merged_people),
        agreement_score=overall_agreement_score,
        disagreements=all_disagreements,
        validation_errors=_validate(overall_agreement_score),
    )


# --- Helpers for main ---

def _resolve_identity_names(context: PeopleCollectorContext) -> Dict[str, List[str]]:
    research_identities = {
        official.name: [official.name]
        for official in context.data.research_municipality_step.elected_officials
    }
    return context.data.config.identities or research_identities


def _merge_groups(
    groups: List[GroupByLLM],
    jurisdiction_ocdid: str,
    people_by_llm: Dict[str, List[Person]],
) -> Tuple[List[Person], Dict]:
    merged_people = []
    all_disagreements = {}

    for group_by_llm in groups:
        flat_group = [p for people in group_by_llm.values() for p in people]
        merged = merge_group_across_llms(flat_group, jurisdiction_ocdid)

        if not merged.roles:
            continue

        merged_people.append(merged)

        comparisons = record_comparison.collect_field_comparisons(
            merged, group_by_llm, FIELDS_TO_CHECK, FIELD_WEIGHTS
        )
        if comparisons:
            all_disagreements[merged.name] = comparisons

    return merged_people, all_disagreements


def _validate(score: float) -> List[str]:
    if score < MINIMUM_AGREEMENT_SCORE:
        return [f"Overall agreement score {score:.2f}% is below the minimum threshold of {MINIMUM_AGREEMENT_SCORE}%."]
    return []


# --- Grouping ---

def group_records_across_llms(
    identity_names: Dict[str, List[str]],
    people_by_llm: Dict[str, List[Person]],
) -> List[GroupByLLM]:
    """
    Group records across LLMs by canonical name, using identity config and fuzzy matching.
    Returns a list of groups, each mapping LLM -> List[Person].
    """
    all_people: List[PersonWithSource] = [
        (person, llm)
        for llm, people in people_by_llm.items()
        for person in people
    ]

    if not all_people:
        return []

    canonical_map = name_utils.build_canonical_map(
        [p for p, _ in all_people],
        identity_names,
    )

    groups: Dict[str, GroupByLLM] = {}
    for person, llm in all_people:
        canonical = canonical_map[person.name]
        groups.setdefault(canonical, {}).setdefault(llm, []).append(person)

    return list(groups.values())


# --- Merging ---

def merge_group_across_llms(group: List[Person], jurisdiction_ocdid: str) -> Person:
    """Merge a group of weakly-tied Person objects into a single Person."""
    canonical_map = name_utils.build_canonical_map(group, {})
    canonical_name = Counter(canonical_map.values()).most_common(1)[0][0]
    other_names = name_utils.collect_other_names(group, canonical_name)

    image = Counter(p.image for p in group if p.image).most_common(1)
    source_urls = {url for p in group if p.source_urls for url in p.source_urls}

    return Person(
        name=canonical_name,
        other_names=other_names,
        roles=field_mergers.merge_field_to_list([p.roles for p in group if p.roles]),
        designations=field_mergers.merge_field_to_list([p.designations for p in group if p.designations]),
        emails=field_mergers.merge_field_to_list([p.emails for p in group if p.emails]),
        phones=field_mergers.merge_field_to_list([p.phones for p in group if p.phones]),
        urls=merge_urls([p.urls for p in group if p.urls]),
        start_date=field_mergers.merge_field("start_date", [p.start_date for p in group if p.start_date]),
        end_date=field_mergers.merge_field("end_date", [p.end_date for p in group if p.end_date]),
        image=image[0][0] if image else "",
        cdn_image="",
        jurisdiction_ocdid=jurisdiction_ocdid,
        source_urls=source_urls,
        updated_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
    )


def merge_urls(url_groups: List[List[str]]) -> List[str]:
    """Prefer URLs appearing in multiple sources; fall back to the most common single URL."""
    url_counter = Counter(url for urls in url_groups for url in urls)
    if not url_counter:
        return []
    multi_source = [url for url, count in url_counter.items() if count > 1]
    return multi_source or [url_counter.most_common(1)[0][0]]