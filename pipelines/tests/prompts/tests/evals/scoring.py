"""Pure scoring for the officials eval: per-person scores and their aggregation.

No I/O and no network, so it is unit-testable directly. Split out of the eval module, which
was 889 lines against a 400-line ceiling — most of it this logic plus a second copy of it
that re-derived the same numbers by reloading saved output from disk.

Owns the eval taxonomy so there is exactly one, shared with the eval module rather than
built twice.
"""

from typing import List

import phonenumbers
from accuracy import build_eval_taxonomy
from runners.people_collector.schemas import RawLLMPersonRecord
from shared.utils import name_utils
from utils.taxonomy import normalize_designations, normalize_roles

EVAL_TAXONOMY = build_eval_taxonomy()


def score_cases(actual: List[RawLLMPersonRecord], expected: List[RawLLMPersonRecord]):
    scores = []
    # Build a lookup for actual people by normalized name
    actual_by_norm_name = {
        name_utils.normalize_name(a_person.name): a_person for a_person in actual
    }
    for e_person in expected:
        norm_name = name_utils.normalize_name(e_person.name)
        a_person = actual_by_norm_name.get(norm_name)
        if a_person:
            score = score_case(a_person, e_person)
        else:
            score = {
                # A person the model failed to return at all scores 0 on every dimension
                # it was expected to carry. Omitting a key here is not neutral — aggregate()
                # averages over the people that carry it, so a dropped key inflates that
                # dimension. The precision keys are deliberately absent: there is no answer
                # to be precise about, and the misses are already counted by recall.
                "scores": {
                    "name": 0.0,
                    "roles": 0.0,
                    "designations": 0.0,
                    "email": 0.0,
                    "phone": 0.0,
                    "url": 0.0,
                    # recall-only: a missed person still counts as a miss for any value
                    # they were expected to carry, but must not invent a denominator for
                    # the ones they weren't.
                    **{
                        f: 0.0
                        for f in ("start_date", "end_date", "image")
                        if getattr(e_person, f, None)
                    },
                },
                "actual": {
                    "name": "",
                    "roles": [],
                    "designations": [],
                    "email": "",
                    "phone": "",
                    "url": "",
                    "start_date": "",
                    "end_date": "",
                    "image": "",
                },
                "expected": {
                    "name": e_person.name,
                    "roles": e_person.roles,
                    "designations": e_person.designations,
                    "email": e_person.email,
                    "phone": e_person.phone,
                    "url": e_person.url,
                    "start_date": e_person.start_date,
                    "end_date": e_person.end_date,
                    "image": e_person.image,
                },
                "person_name": e_person.name,
            }
        scores.append(score)
    return scores


def _set_precision(score: dict, key: str, actual_values, expected_values) -> None:
    """Share of what the model returned that was actually wanted.

    `roles` and `designations` are recall — matched over *expected* — so over-generation is
    free: four roles for a one-role person still scores 1.0. Omitted when the model
    returned nothing, since precision is undefined over an empty answer and recall already
    rewards a correct absence.
    """
    if not actual_values:
        return
    matching = set(actual_values) & set(expected_values)
    score[key] = len(matching) / len(set(actual_values))


def score_case(actual: RawLLMPersonRecord, expected: RawLLMPersonRecord):
    score = {}
    actual_vals = {}
    expected_vals = {}

    # name (normalized)
    actual_name_norm = name_utils.normalize_name(actual.name)
    expected_name_norm = name_utils.normalize_name(expected.name)
    score["name"] = 1.0 if actual_name_norm == expected_name_norm else 0.0
    actual_vals["name"] = actual.name
    expected_vals["name"] = expected.name

    # roles (set match)
    actual_roles = normalize_roles(actual.roles, EVAL_TAXONOMY)
    expected_roles = normalize_roles(expected.roles, EVAL_TAXONOMY)
    matching_roles = set(actual_roles) & set(expected_roles)
    score["roles"] = (
        len(matching_roles) / len(expected_roles) if expected_roles else 1.0
    )
    _set_precision(score, "roles_precision", actual_roles, expected_roles)
    actual_vals["roles"] = actual.roles
    expected_vals["roles"] = expected.roles

    # designations — scored whenever any are expected. There used to be an exemption for
    # cases without "district"/"ward", which handed a free 1.0 to 19 of the 40 people who
    # have designations (Position, Place, At-Large). It had no basis: the prompt always
    # lists the designation vocabulary and gives normalization examples ("Posn. 2" →
    # "Position 2"), so these are asked for explicitly. They are also exactly the
    # non-geographic residue that distinguishes seats in `posts`.
    #
    # Normalized like roles, and for the same reason: raw string equality made every
    # provider lose the same case on a hyphen. Fixtures say "At-Large", every model returns
    # "At Large" — which is what the prompt asks for ("City-Wide" → "At Large") and what
    # designations.yml lists as the alias. The models were right and the scorer was wrong.
    actual_designations = normalize_designations(actual.designations, EVAL_TAXONOMY)
    expected_designations = normalize_designations(expected.designations, EVAL_TAXONOMY)
    if not expected_designations:
        score["designations"] = 1.0
    else:
        score["designations"] = len(
            set(actual_designations) & set(expected_designations)
        ) / len(expected_designations)
    _set_precision(
        score, "designations_precision", actual_designations, expected_designations
    )
    actual_vals["designations"] = actual.designations
    expected_vals["designations"] = expected.designations

    # email
    score["email"] = 1.0 if (actual.email or "") == (expected.email or "") else 0.0
    actual_vals["email"] = actual.email
    expected_vals["email"] = expected.email

    # phone
    actual_phone_parsed = (
        phonenumbers.parse(actual.phone, "US") if actual.phone else None
    )
    expected_phone_parsed = (
        phonenumbers.parse(expected.phone, "US") if expected.phone else None
    )
    score["phone"] = 1.0 if actual_phone_parsed == expected_phone_parsed else 0.0
    actual_vals["phone"] = actual.phone
    expected_vals["phone"] = expected.phone

    # url
    score["url"] = 1.0 if (actual.url or "") == (expected.url or "") else 0.0
    actual_vals["url"] = actual.url
    expected_vals["url"] = expected.url

    # start_date / end_date / image — previously not scored at all, which hid the largest
    # difference between providers: measured 2026-08-14, AtlasCloud extracted 100% of
    # start_dates while DeepInfra and Parasail extracted 0%, yet DeepInfra scored *higher*
    # overall. Plain equality is fair — when a model does extract a date it matches the
    # fixture's format exactly ("2025-05", "2025-01-06"). str() because YAML parses a full
    # date into datetime.date but leaves a partial "2025-05" a string.
    #
    # RECALL ONLY: the key is omitted when nothing is expected, so these measure "of the
    # values that exist, how many did you get". Scoring a correct absence as 1.0 buries the
    # signal — only 12 of 62 people have a start_date, so a model extracting NONE of them
    # still scored 0.77. aggregate() divides by how many scores carry the key.
    for field in ("start_date", "end_date", "image"):
        expected_value = getattr(expected, field) or ""
        if not expected_value:
            continue
        actual_value = getattr(actual, field) or ""
        score[field] = 1.0 if str(actual_value) == str(expected_value) else 0.0
        actual_vals[field] = getattr(actual, field)
        expected_vals[field] = getattr(expected, field)

    return {
        "scores": score,
        "actual": actual_vals,
        "expected": expected_vals,
        "person_name": expected.name,
    }


def aggregate(scores):
    """
    Aggregates the scores from all test cases into a single report.
    Each key in the score dictionary is averaged across all cases.
    If there are multiple people in a case, their scores are averaged first.
    """
    if not scores:
        return {}

    # Aggregate scores for each case.
    #
    # A dimension is averaged over the people that CARRY it, not over everyone. Most fields
    # are present on every person so nothing changes for them; the recall-only ones
    # (start_date, end_date, image) are omitted where nothing is expected, and counting
    # those absences as successes is what let a model extracting zero dates score 0.77.
    case_aggregates = []
    for case_scores in scores:
        if not case_scores:
            continue
        case_aggregate = {}
        all_keys = set()
        for score in case_scores:
            all_keys.update(score["scores"].keys())
        for key in all_keys:
            present = [s["scores"][key] for s in case_scores if key in s["scores"]]
            if present:
                case_aggregate[key] = sum(present) / len(present)
        case_aggregates.append(case_aggregate)

    # Aggregate across cases — same rule, since a whole case may carry no dates at all.
    if not case_aggregates:
        return {}

    final_aggregate = {}
    for key in {k for case in case_aggregates for k in case}:
        present = [case[key] for case in case_aggregates if key in case]
        final_aggregate[key] = sum(present) / len(present)

    return final_aggregate



def failing_people(case_scores_by_id: dict, thresholds: dict) -> list[dict]:
    """Fields that scored below their floor, built from the scores already computed.

    This replaces a ~300-line loop that reloaded each provider's saved `-actual.yml` and
    re-scored every person from scratch — a second implementation of score_case that could
    drift from the first, and did: it kept a `has_district_or_ward` exemption written as
    `d in ["district", "ward"]`, comparing a whole designation to a bare word, so it never
    matched and those fields scored a permanent 1.0.
    """
    failures = []
    for case_id, people in sorted(case_scores_by_id.items()):
        for person in people:
            for field, floor in thresholds.items():
                score = person["scores"].get(field)
                if score is None or score >= floor:
                    continue
                failures.append(
                    {
                        "case_id": case_id,
                        "person": person.get("person_name"),
                        "field": field,
                        "score": score,
                        "threshold": floor,
                        "expected": person["expected"].get(field),
                        "actual": person["actual"].get(field),
                    }
                )
    return failures
