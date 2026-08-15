import asyncio
import os
import pathlib
import time
from typing import List, cast

import phonenumbers
import pytest
import pytest_asyncio
import yaml
from eval_utils import (
    PROVIDER_COMPARISON,
    make_provider_client,
    write_comparison_report,
)
from runners.people_collector.schemas import (
    PeopleArrayLLMResponseSchema,
    RawLLMPersonRecord,
)
from services.open_router.llm import run_prompt as run_together_prompt
from services.open_router.prompts import municipality_officials_prompt
from shared.schemas import Role, RoleConfig
from shared.utils import name_utils
from utils import cost_utils
from accuracy import (
    as_report,
    build_eval_taxonomy,
    case_dispositions,
    merge_dispositions,
    summarize,
)
from utils.taxonomy import (
    Taxonomy,
    build_taxonomy,
    normalize_designations,
    normalize_roles,
)

pytestmark = pytest.mark.evals

ROLE_ALIASES_PATH = pathlib.Path("tests/prompts/datasets/local/role_aliases.yml")

# The prompt asks for *currently serving* officials, so its answer depends on the date it
# is run. Pinned here, because otherwise the fixtures rot: 9 of 62 expected people have
# terms that have now ended (board_of_aldermen 3/5, mixed_current_past 3/6,
# redundant_place_role 3/6), and a model correctly applying today's date would be marked
# wrong for excluding them. Must sit in [latest expected start_date, earliest expected
# end_date) = ["2025-05", "2026").
EVAL_CURRENT_DATE = "2025-09-01"


def make_together_prompt(known_roles):
    return municipality_officials_prompt(known_roles, current_date=EVAL_CURRENT_DATE)


EVAL_TAXONOMY = build_eval_taxonomy()

# F1 floors on the disposition scoring — "is this provider fit to run in production", not a
# quality target. A provider below one of these is unfit, which is why DeepInfra's 0.000 on
# both dates is meant to fail rather than be accommodated.
#
# Two tiers, because roles and district are what the posts/memberships model is built on
# and everything else is supporting detail. That is a priority ordering, not a claim the
# rest does not matter — every field is gated.
#
# Numbers carry headroom for run-to-run drift, measured 2026-08-15 across two identical
# runs: roles 0.027, designations 0.077, url 0.154, end_date 0.133, image 0.500. A
# threshold set tighter than its drift will flap for reasons that have nothing to do with
# the prompt. `image` is deliberately loose for exactly that reason; tighten it only after
# temperature and seed are pinned.
ACCURACY_THRESHOLDS = {
    # Tier 1 — what the product is built on. Measured 0.976–0.992 and 0.977–1.000.
    "roles": 0.94,
    "district": 0.92,
    # Tier 2 — gated, with room. Measured across all three providers 2026-08-15.
    "person": 0.94,
    "designations_other": 0.75,
    "email": 0.60,
    "phone": 0.50,
    "url": 0.55,
    # Extracting none of the twelve dates that exist is a real 0.0, not "unmeasured".
    # DeepInfra does exactly that and is meant to fail here.
    "start_date": 0.50,
    "end_date": 0.50,
    "image": 0.70,
}


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


def _progress(name: str, message: str) -> None:
    """Cases run concurrently under asyncio.gather, so a bare print says nothing about how
    far along the run is. Every line carries the provider, a done/total count and elapsed
    seconds, and flushes — pytest buffers otherwise and you see the lot at the end."""
    done, total = _PROGRESS[name]
    elapsed = time.time() - _RUN_STARTED_AT
    print(f"[{elapsed:6.1f}s] {name:26} {done:>2}/{total:<2} {message}", flush=True)


_PROGRESS: dict = {}
_RUN_STARTED_AT = time.time()


async def _run_single_case(model_client, case, ocdid):
    run_prompt = model_client["run_prompt"]
    make_prompt = model_client["make_prompt"]
    extra_kwargs = model_client.get("extra_kwargs", {})
    name = model_client["name"]

    _progress(name, f"START  {case['id']}")
    started = time.time()

    known_roles = case["expected"].get("known_roles", [])
    prompt = make_prompt(known_roles)
    try:
        response = await run_prompt(
            "run-eval",
            ocdid,
            prompt,
            response_schema=PeopleArrayLLMResponseSchema,
            content=case["input"],
            **extra_kwargs,
        )
    except Exception as exc:
        # Surface which case died and why. gather() would otherwise report one exception
        # for the whole batch with no indication of which provider or case produced it.
        _PROGRESS[name][0] += 1
        _progress(name, f"FAILED {case['id']} after {time.time() - started:.1f}s: {exc!r}")
        raise

    _PROGRESS[name][0] += 1
    _progress(name, f"done   {case['id']} in {time.time() - started:.1f}s")
    expected = [RawLLMPersonRecord(**person) for person in case["expected"]["people"]]
    actual = cast(PeopleArrayLLMResponseSchema, response)
    case_path = case.get("case_path", "unknown_case")
    with open(
        f"{case_path}/{model_client['name']}-actual.yml", "w", encoding="utf-8"
    ) as f:
        yaml_output = yaml.safe_dump(
            PeopleArrayLLMResponseSchema.model_dump(actual), sort_keys=False
        )
        f.write(yaml_output)

    case_scores = score_cases(actual.people, expected)
    case_aggregate = {}
    if not expected and actual.people:
        case_aggregate["hallucination"] = 0.0
    else:
        # Same present-keys rule as aggregate(). This used to default a missing key to 0.0
        # and divide by everyone, so the per-case breakdown in each report diluted the
        # recall-only dimensions while the overall report did not — the two numbers
        # disagreed for the same run.
        all_keys = set()
        for score in case_scores:
            all_keys.update(score["scores"].keys())
        for key in all_keys:
            present = [s["scores"][key] for s in case_scores if key in s["scores"]]
            if present:
                case_aggregate[key] = sum(present) / len(present)

    dispositions = case_dispositions(actual.people, expected, EVAL_TAXONOMY)
    return case["id"], case_aggregate, case_scores, dispositions


@pytest.mark.asyncio
async def run_eval(
    model_client,
    cases,
    ocdid="ocd-jurisdiction/country:us/state:tx/place:example/government",
):
    name = model_client["name"]
    _PROGRESS[name] = [0, len(cases)]
    batch_started = time.time()
    # Costs key on the ocdid, which every provider shares, so without this each report
    # carries the previous providers' tokens too and cost ranking becomes run order.
    cost_utils.reset_cost_tracker(ocdid)
    _progress(name, f"dispatching {len(cases)} cases concurrently")

    results = await asyncio.gather(
        *[_run_single_case(model_client, case, ocdid) for case in cases]
    )

    _progress(name, f"ALL DONE in {time.time() - batch_started:.1f}s")
    per_case_scores = [(case_id, agg) for case_id, agg, _, _ in results]
    scores = [case_scores for _, _, case_scores, _ in results]
    # Dispositions are counted across every person in the run, not averaged per case —
    # precision has no meaning inside one case that produced nothing.
    accuracy = summarize(merge_dispositions([d for _, _, _, d in results]))
    return aggregate(scores), per_case_scores, accuracy


@pytest_asyncio.fixture
def load_eval_cases(base_dir="tests/prompts/datasets/local/municipal_officials"):
    base = pathlib.Path(base_dir)
    only_case = os.environ.get("EVAL_CASE")
    cases = []

    for case_dir in sorted(base.iterdir()):
        if only_case and case_dir.name != only_case:
            continue
        print(f"Loading case from {case_dir}")
        if not case_dir.is_dir():
            continue

        input_path = case_dir / "input.md"
        expected_path = case_dir / "expected.yml"

        if not input_path.exists() or not expected_path.exists():
            raise ValueError(f"Missing input.txt or expected.yml in {case_dir}")

        with open(expected_path, "r", encoding="utf-8") as f:
            expected_content = yaml.safe_load(f)

        case = {
            "id": case_dir.name,
            "case_path": str(case_dir),
            "input": input_path.read_text(encoding="utf-8"),
            "expected": expected_content,
        }

        cases.append(case)

    return cases


@pytest_asyncio.fixture
async def model_client(request):
    if request.param == "gemini":
        return {
            "name": "gemini",
            "run_prompt": run_gemini_prompt,
            "make_prompt": make_gemini_prompt,
        }
    elif request.param == "open_router":
        return {
            "name": "open_router",
            "run_prompt": run_together_prompt,
            "make_prompt": make_together_prompt,
        }
    elif request.param.startswith("open_router:"):
        provider = request.param.split(":", 1)[1]
        return {
            "name": f"open_router-{provider}",
            "run_prompt": run_together_prompt,
            "make_prompt": make_together_prompt,
            "extra_kwargs": {
                "model_type": "STANDARD",
                "provider_order": [provider],
                "allow_fallbacks": False,
            },
        }
    else:
        raise ValueError(f"Unknown model client: {request.param}")


def _active_providers():
    only = os.environ.get("EVAL_PROVIDER")
    return [p for p in PROVIDER_COMPARISON if not only or p.split(":", 1)[1] == only]


@pytest.mark.parametrize("model_client", _active_providers(), indirect=True)
@pytest.mark.asyncio
async def test_eval_with_mocked_cases(model_client, load_eval_cases):
    start_time = time.time()
    report, per_case_scores, accuracy = await run_eval(model_client, load_eval_cases)
    elapsed_seconds = round(time.time() - start_time, 2)
    print("Final aggregated report:", report)

    # Every field is gated. The tiers below say how much room each one gets, not whether it
    # matters — see ACCURACY_THRESHOLDS for the split.
    #
    # A 0.0 threshold means "report it, don't gate on it". The precision dimensions stay
    # there because raising them also means teaching the per-case failure loop below to
    # compute them — it reads each key off the record, and neither exists there, so it
    # scores them a silent 1.0 (as it already does for `hallucination`).
    thresholds = {
        "name": 0.80,
        "roles": 0.90,
        "designations": 0.85,
        "email": 0.80,
        "phone": 0.80,
        "url": 0.0,
        "start_date": 0.0,
        "end_date": 0.0,
        "image": 0.0,
        "roles_precision": 0.0,
        "designations_precision": 0.0,
        "hallucination": 1.0,
    }

    failed_cases = []
    for idx, (case_id, case_aggregate) in enumerate(per_case_scores):
        failed = []
        # Load the actual and expected people for this case
        # You need to reload the actual/expected people to get the details for reporting
        case = next(c for c in load_eval_cases if c["id"] == case_id)
        expected_people = [
            RawLLMPersonRecord(**person) for person in case["expected"]["people"]
        ]
        actual_path = os.path.join(
            case["case_path"], f"{model_client['name']}-actual.yml"
        )
        if os.path.exists(actual_path):
            with open(actual_path, "r", encoding="utf-8") as f:
                actual_people = yaml.safe_load(f).get("people", [])
        else:
            actual_people = []

        # Hallucination check: expected empty but model returned people
        if not expected_people and actual_people:
            failed.append(
                {
                    "person": None,
                    "field": "hallucination",
                    "expected": [],
                    "actual": [p.get("name") for p in actual_people],
                }
            )

        # Build lookup for actual people by normalized name
        actual_by_norm_name = {
            name_utils.normalize_name(a.get("name", "")): a for a in actual_people
        }

        for e_person in expected_people:
            norm_name = name_utils.normalize_name(e_person.name)
            a_person = actual_by_norm_name.get(norm_name, {})
            for key, threshold in thresholds.items():
                actual_val = a_person.get(key, "") if a_person else ""
                expected_val = getattr(e_person, key, "")
                # Treat null and '' as equal
                if (actual_val is None or actual_val == "") and (
                    expected_val is None or expected_val == ""
                ):
                    score = 1.0
                elif key == "name":
                    score = (
                        1.0
                        if norm_name == name_utils.normalize_name(actual_val)
                        else 0.0
                    )
                elif key == "roles":
                    actual_roles = normalize_roles(a_person.get("roles", []), EVAL_TAXONOMY)
                    expected_roles = normalize_roles(getattr(e_person, "roles", []), EVAL_TAXONOMY)
                    matching_roles = set(actual_roles) & set(expected_roles)
                    score = (
                        len(matching_roles) / len(expected_roles)
                        if expected_roles
                        else 1.0
                    )
                elif key == "designations":
                    actual_designations = normalize_designations(
                        a_person.get("designations", []), EVAL_TAXONOMY
                    )
                    expected_designations = normalize_designations(
                        getattr(e_person, "designations", []), EVAL_TAXONOMY
                    )
                    if not expected_designations:
                        score = 1.0
                    else:
                        score = len(
                            set(actual_designations) & set(expected_designations)
                        ) / len(expected_designations)
                elif key == "email":
                    score = 1.0 if actual_val == expected_val else 0.0
                elif key == "phone":
                    try:
                        actual_phone_parsed = (
                            phonenumbers.parse(actual_val, "US") if actual_val else None
                        )
                        expected_phone_parsed = (
                            phonenumbers.parse(expected_val, "US")
                            if expected_val
                            else None
                        )
                        score = (
                            1.0 if actual_phone_parsed == expected_phone_parsed else 0.0
                        )
                    except Exception:
                        score = 0.0
                elif key == "url":
                    score = 1.0 if actual_val == expected_val else 0.0
                else:
                    score = 0.0

                if score < threshold:
                    failed.append(
                        {
                            "person": e_person.name,
                            "field": key,
                            "expected": expected_val,
                            "actual": actual_val,
                        }
                    )

        if failed:
            failed_cases.append(
                {
                    "model_client": model_client["name"],
                    "case_number": idx,
                    "case_id": case_id,
                    "failures": failed,
                }
            )

    aggregate_failures = []
    aggregate_failed_cases = {}

    for field, threshold in thresholds.items():
        actual_score = report.get(field, 0.0)
        if actual_score < threshold:
            aggregate_failures.append(
                {"field": field, "actual": actual_score, "threshold": threshold}
            )
            # Collect all failed field instances across all cases
            field_failures = []
            for idx, (case_id, case_aggregate) in enumerate(per_case_scores):
                # Reload expected and actual people for this case
                case = next(c for c in load_eval_cases if c["id"] == case_id)
                expected_people = [
                    RawLLMPersonRecord(**person)
                    for person in case["expected"]["people"]
                ]
                actual_path = os.path.join(
                    case["case_path"], f"{model_client['name']}-actual.yml"
                )
                if os.path.exists(actual_path):
                    with open(actual_path, "r", encoding="utf-8") as f:
                        actual_people = yaml.safe_load(f).get("people", [])
                else:
                    actual_people = []
                actual_by_norm_name = {
                    name_utils.normalize_name(a.get("name", "")): a
                    for a in actual_people
                }
                for e_person in expected_people:
                    norm_name = name_utils.normalize_name(e_person.name)
                    a_person = actual_by_norm_name.get(norm_name, {})
                    actual_val = a_person.get(field, "") if a_person else ""
                    expected_val = getattr(e_person, field, "")
                    # Treat null and '' as equal
                    if (actual_val is None or actual_val == "") and (
                        expected_val is None or expected_val == ""
                    ):
                        score = 1.0
                    elif field == "name":
                        score = (
                            1.0
                            if norm_name == name_utils.normalize_name(actual_val)
                            else 0.0
                        )
                    elif field == "roles":
                        actual_roles = normalize_roles(a_person.get("roles", []), EVAL_TAXONOMY)
                        expected_roles = normalize_roles(getattr(e_person, "roles", []), EVAL_TAXONOMY)
                        matching_roles = set(actual_roles) & set(expected_roles)
                        score = (
                            len(matching_roles) / len(expected_roles)
                            if expected_roles
                            else 1.0
                        )
                    elif field == "designations":
                        actual_designations = normalize_designations(
                            a_person.get("designations", []), EVAL_TAXONOMY
                        )
                        expected_designations = normalize_designations(
                            getattr(e_person, "designations", []), EVAL_TAXONOMY
                        )
                        if not expected_designations:
                            score = 1.0
                        else:
                            score = len(
                                set(actual_designations) & set(expected_designations)
                            ) / len(expected_designations)
                    elif field == "email":
                        score = 1.0 if actual_val == expected_val else 0.0
                    elif field == "phone":
                        try:
                            actual_phone_parsed = (
                                phonenumbers.parse(actual_val, "US")
                                if actual_val
                                else None
                            )
                            expected_phone_parsed = (
                                phonenumbers.parse(expected_val, "US")
                                if expected_val
                                else None
                            )
                            score = (
                                1.0
                                if actual_phone_parsed == expected_phone_parsed
                                else 0.0
                            )
                        except Exception:
                            score = 0.0
                    elif field == "url":
                        score = 1.0 if actual_val == expected_val else 0.0
                    else:
                        score = 0.0

                    if score < threshold:
                        field_failures.append(
                            {
                                "case_id": case_id,
                                "person": e_person.name,
                                "expected": expected_val,
                                "actual": actual_val,
                            }
                        )
            aggregate_failed_cases[field] = field_failures

    # Write full report to file
    eval_ocdid = "ocd-jurisdiction/country:us/state:tx/place:example/government"
    llm_costs = cost_utils.get_cost_tracker(eval_ocdid)["llm_costs"]
    cost_summary = {
        "model": llm_costs[0]["model"] if llm_costs else None,
        "elapsed_seconds": elapsed_seconds,
        "total_input_tokens": sum(c["input_tokens"] for c in llm_costs),
        "total_output_tokens": sum(c["output_tokens"] for c in llm_costs),
        "total_cost_usd": float(sum(c["total_cost"] for c in llm_costs)),
    }

    evals_dir = "tests/prompts/tests/evals/municipal_officials"
    os.makedirs(evals_dir, exist_ok=True)
    report_path = os.path.join(evals_dir, f"{model_client['name']}-eval-report.yml")
    with open(report_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "cost_summary": cost_summary,
                "aggregated_report": report,
                "aggregate_failures": aggregate_failures,
                "aggregate_failed_cases": aggregate_failed_cases,
                "per_case_scores": [
                    {"case_id": case_id, "scores": case_aggregate}
                    for case_id, case_aggregate in per_case_scores
                ],
                "failed_cases": failed_cases,
            },
            f,
            sort_keys=False,
        )
    print(f"Saved evaluation report to {report_path}")

    # Assert thresholds
    assert report["name"] >= thresholds["name"]
    assert report["roles"] >= thresholds["roles"]
    assert report["designations"] >= thresholds["designations"]
    assert report["email"] >= thresholds["email"]
    assert report["phone"] >= thresholds["phone"]
    assert report["url"] >= thresholds["url"]
    # .get(): conditionally scored, so the key is absent when no case supplied a
    # denominator — nothing expected (dates, image) or nothing returned (precision).
    assert report.get("start_date", 1.0) >= thresholds["start_date"]
    assert report.get("end_date", 1.0) >= thresholds["end_date"]
    assert report.get("image", 1.0) >= thresholds["image"]
    assert report.get("roles_precision", 1.0) >= thresholds["roles_precision"]
    assert report.get("designations_precision", 1.0) >= thresholds["designations_precision"]

    # Accuracy gates. Reported before asserting so a failure shows the whole picture rather
    # than only the first field that tripped.
    print("Accuracy (disposition scoring):", as_report(accuracy))
    below = [
        f"{field}: F1={accuracy[field].f1:.3f} < {floor:.2f} "
        f"(correct={accuracy[field].correct} missing={accuracy[field].false_negative} "
        f"spurious={accuracy[field].false_positive} wrong={accuracy[field].wrong_match})"
        for field, floor in ACCURACY_THRESHOLDS.items()
        # f1 is None only when a field had no comparisons at all — nothing wanted and
        # nothing produced, which is unjudgeable. Producing nothing where something *was*
        # wanted scores a real 0.0 and fails here; see Tally.f1 for why that needed care.
        if accuracy[field].f1 is not None and accuracy[field].f1 < floor
    ]
    assert not below, "Accuracy below threshold:\n  " + "\n  ".join(below)
    assert (
        len(
            [
                c
                for c in failed_cases
                if any(f["field"] == "hallucination" for f in c["failures"])
            ]
        )
        == 0
    ), "Model returned people when expected empty"


async def _run_provider(client, cases):
    # The provider goes in the place slug, not a segment of its own. Costs key on the
    # ocdid and the three providers run concurrently, so they do need distinct ones — but
    # `.../place:example/{provider}/government` is not a valid ocdid: id_utils requires
    # every middle segment to be `label:value`. It parsed until a209e141e added state and
    # county parsing, and has raised on the first case of every provider ever since.
    ocdid = f"ocd-jurisdiction/country:us/state:tx/place:example_{client['name']}/government"
    start_time = time.time()
    report, per_case_scores, accuracy = await run_eval(client, cases, ocdid)
    elapsed_seconds = round(time.time() - start_time, 2)
    llm_costs = cost_utils.get_cost_tracker(ocdid)["llm_costs"]
    return {
        "client": client,
        "report": report,
        "accuracy": accuracy,
        "per_case_scores": per_case_scores,
        "elapsed_seconds": elapsed_seconds,
        "llm_costs": llm_costs,
    }


@pytest.mark.asyncio
async def test_provider_comparison(load_eval_cases):
    """Runs all providers concurrently and writes one report per provider."""
    clients = [
        make_provider_client(p, make_together_prompt) for p in PROVIDER_COMPARISON
    ]
    results = await asyncio.gather(
        *[_run_provider(c, load_eval_cases) for c in clients], return_exceptions=True
    )

    evals_dir = "tests/prompts/tests/evals/municipal_officials"
    os.makedirs(evals_dir, exist_ok=True)

    comparison = {}
    failures = {}
    for client, result in zip(clients, results):
        if isinstance(result, Exception):
            # Record it, don't just print. An all-failed run used to leave
            # `providers: {}` in comparison.yml with no indication that anything had gone
            # wrong — it read as "no data" rather than "everything blew up".
            failures[client["name"]] = repr(result)
            print(f"PROVIDER FAILED: {client['name']}: {result!r}", flush=True)
            continue
        llm_costs = result["llm_costs"]
        cost_summary = {
            "model": llm_costs[0]["model"] if llm_costs else None,
            "elapsed_seconds": result["elapsed_seconds"],
            "total_input_tokens": sum(c["input_tokens"] for c in llm_costs),
            "total_output_tokens": sum(c["output_tokens"] for c in llm_costs),
            "total_cost_usd": float(sum(c["total_cost"] for c in llm_costs)),
        }
        report_path = os.path.join(evals_dir, f"{client['name']}-eval-report.yml")
        with open(report_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                {
                    "cost_summary": cost_summary,
                    "accuracy": as_report(result["accuracy"]),
                    "aggregated_report": result["report"],
                    "per_case_scores": [
                        {"case_id": case_id, "scores": case_aggregate}
                        for case_id, case_aggregate in result["per_case_scores"]
                    ],
                },
                f,
                sort_keys=False,
            )
        print(f"Saved provider comparison report to {report_path}")
        comparison[client["name"]] = {
            "elapsed_seconds": result["elapsed_seconds"],
            "cost_usd": cost_summary["total_cost_usd"],
            # F1 on the two dimensions the product depends on, first — the overall figure
            # is dominated by contact fields and ranks providers differently.
            "f1_roles": result["accuracy"]["roles"].f1,
            "f1_district": result["accuracy"]["district"].f1,
            **result["report"],
        }

    write_comparison_report(evals_dir, comparison, failures)

    # Without this the test passes when every provider dies — which is exactly what it did
    # while the ocdid above was invalid: 45 cases raised, nothing ran, green in 0.18s.
    assert not failures, f"Providers failed: {failures}"
