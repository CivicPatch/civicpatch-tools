from typing import List, Dict
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

# --- Types ---

PersonWithSource = tuple[Person, str]
GroupByLLM = Dict[str, List[Person]]


# --- Main entry point ---

def merge_records_across_llms(context: PeopleCollectorContext) -> MergeRecordsAcrossLLMsStep:
    """Merge records across all LLMs to produce a unified list of Person objects."""
    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    people_by_llm: Dict[str, List[Person]] = context.data.merge_records_within_llm_step.people_by_llm
    identity_names = _resolve_identity_names(context)

    groups = group_records_across_llms(identity_names, people_by_llm)
    groups = merge_weak_tie_groups(groups)
    merged_people = _merge_groups(groups, jurisdiction_ocdid)

    return MergeRecordsAcrossLLMsStep(
        people=people_utils.sort_people(merged_people),
    )


# --- Helpers for main ---

def _resolve_identity_names(context: PeopleCollectorContext) -> Dict[str, List[str]]:
    return context.data.prepare_pipeline_step.identities


def _merge_groups(
    groups: List[GroupByLLM],
    jurisdiction_ocdid: str,
) -> List[Person]:
    merged_people = []

    for group_by_llm in groups:
        flat_group = [p for people in group_by_llm.values() for p in people]
        merged = merge_group_across_llms(flat_group, jurisdiction_ocdid)

        if not merged.roles:
            continue

        merged_people.append(merged)

    return merged_people


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

def merge_weak_tie_groups(groups: List[GroupByLLM]) -> List[GroupByLLM]:
    """
    Merge last-name-only groups into full-name groups when they share the same
    last name and at least one (role, designation) pair.
    """
    def flat_people(group: GroupByLLM) -> List[Person]:
        return [p for people in group.values() for p in people]

    def is_last_name_only(name: str) -> bool:
        return len(name.split()) == 1

    def parsed_last_name(name: str) -> str:
        parsed = name_utils.parse_name(name)
        return parsed.last.lower() if parsed.last else name.split()[-1].lower()

    def role_designation_pairs(group: GroupByLLM) -> set:
        result = set()
        for p in flat_people(group):
            for r in (p.roles or []):
                for d in (p.designations or [""]):
                    result.add((r, d))
        return result

    def is_weak_group(group: GroupByLLM) -> bool:
        return all(is_last_name_only(p.name) for p in flat_people(group))

    merge_into: Dict[int, int] = {}

    for wi, weak in enumerate(groups):
        if not is_weak_group(weak):
            continue
        weak_last_names = {p.name.lower() for p in flat_people(weak)}
        weak_pairs = role_designation_pairs(weak)
        if not weak_pairs:
            continue
        for si, strong in enumerate(groups):
            if si == wi or is_weak_group(strong):
                continue
            strong_last_names = {parsed_last_name(p.name) for p in flat_people(strong)}
            if not weak_last_names & strong_last_names:
                continue
            if not weak_pairs & role_designation_pairs(strong):
                continue
            merge_into[wi] = si
            break

    if not merge_into:
        return groups

    result = [dict(g) for g in groups]
    for wi, si in merge_into.items():
        for llm, people in groups[wi].items():
            result[si].setdefault(llm, []).extend(people)

    return [g for i, g in enumerate(result) if i not in merge_into]


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