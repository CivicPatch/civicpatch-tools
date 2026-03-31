import pytest
import pytest_asyncio
from utils import merge_utils, cost_utils
from services.google_gemini.llm import run_prompt as run_gemini_prompt
from services.google_gemini.prompts import municipality_officials_prompt as make_gemini_prompt
from services.together_ai.llm import run_prompt as run_together_prompt
from services.together_ai.prompts import municipality_officials_prompt as make_together_prompt
from jobs.people_collector.schemas import PeopleArrayLLMResponseSchema, RawLLMPerson
import phonenumbers
from typing import cast, List
import pathlib
import yaml
import os
from shared.utils import name_utils
import utils.merge_utils 
import utils.people_utils

pytestmark = pytest.mark.evals

def score_cases(actual: List[RawLLMPerson], expected: List[RawLLMPerson]):
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
                "scores": {
                    "name": 0.0,
                    "roles": 0.0,
                    "designations": 0.0,
                    "email": 0.0,
                    "phone": 0.0,
                    "url": 0.0
                },
                "actual": {
                    "name": "",
                    "roles": [],
                    "designations": [],
                    "email": "",
                    "phone": "",
                    "url": ""
                },
                "expected": {
                    "name": e_person.name,
                    "roles": e_person.roles,
                    "designations": e_person.designations,
                    "email": e_person.email,
                    "phone": e_person.phone,
                    "url": e_person.url
                },
                "person_name": e_person.name
            }
        scores.append(score)
    return scores

def score_case(actual: RawLLMPerson, expected: RawLLMPerson):
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
    actual_roles = utils.people_utils.normalize_roles(actual.roles)
    expected_roles = utils.people_utils.normalize_roles(expected.roles)
    matching_roles = set(actual_roles) & set(expected_roles)
    score["roles"] = len(matching_roles) / len(expected_roles) if expected_roles else 1.0
    actual_vals["roles"] = actual.roles
    expected_vals["roles"] = expected.roles

    # designations
    has_district_or_ward = any(d in ["district", "ward"] for d in expected.designations)
    if not expected.designations or not has_district_or_ward:
        score["designations"] = 1.0
    else:
        score["designations"] = len(set(actual.designations) & set(expected.designations)) / len(expected.designations)
    actual_vals["designations"] = actual.designations
    expected_vals["designations"] = expected.designations

    # email
    score["email"] = 1.0 if (actual.email or "") == (expected.email or "") else 0.0
    actual_vals["email"] = actual.email
    expected_vals["email"] = expected.email

    # phone
    actual_phone_parsed = phonenumbers.parse(actual.phone, "US") if actual.phone else None
    expected_phone_parsed = phonenumbers.parse(expected.phone, "US") if expected.phone else None
    score["phone"] = 1.0 if actual_phone_parsed == expected_phone_parsed else 0.0
    actual_vals["phone"] = actual.phone
    expected_vals["phone"] = expected.phone

    # url
    score["url"] = 1.0 if (actual.url or "") == (expected.url or "") else 0.0
    actual_vals["url"] = actual.url
    expected_vals["url"] = expected.url

    return {
        "scores": score,
        "actual": actual_vals,
        "expected": expected_vals,
        "person_name": expected.name
    }

def aggregate(scores):
    """
    Aggregates the scores from all test cases into a single report.
    Each key in the score dictionary is averaged across all cases.
    If there are multiple people in a case, their scores are averaged first.
    """
    if not scores:
        return {}

    # Aggregate scores for each case
    case_aggregates = []
    for case_scores in scores:
        if not case_scores:
            continue
        case_aggregate = {}
        all_keys = set()
        for score in case_scores:
            all_keys.update(score["scores"].keys())
        for key in all_keys:
            case_aggregate[key] = sum(score["scores"].get(key, 0.0) for score in case_scores) / len(case_scores)
        case_aggregates.append(case_aggregate)

    # Aggregate scores across all cases
    if not case_aggregates:
        return {}

    final_aggregate = {}
    for key in case_aggregates[0].keys():
        final_aggregate[key] = sum(case[key] for case in case_aggregates) / len(case_aggregates)

    return final_aggregate

@pytest.mark.asyncio
async def run_eval(model_client, cases):
    scores = []
    per_case_scores = []
    for case in cases:
        run_prompt = model_client["run_prompt"]
        make_prompt = model_client["make_prompt"] 

        case_input = case["input"]
        prompt = make_prompt([])
        response = await run_prompt(
            "run-eval",
            "ocd-jurisdiction/country:us/state:tx/place:example/government",
            prompt,
            response_schema=PeopleArrayLLMResponseSchema,
            content=case_input
        )
        expected = [RawLLMPerson(**person) for person in case["expected"]["people"]] 
        actual = cast(PeopleArrayLLMResponseSchema, response)
        case_path = case.get("case_path", "unknown_case")
        with open(f"{case_path}/{model_client["name"]}-actual.yml", 'w', encoding='utf-8') as f:
            serialized_output = PeopleArrayLLMResponseSchema.model_dump(actual)
            yaml_output = yaml.safe_dump(serialized_output, sort_keys=False)
            f.write(yaml_output)

        case_scores = score_cases(actual.people, expected)
        # Aggregate scores for this case
        case_aggregate = {}
        all_keys = set()
        for score in case_scores:
            all_keys.update(score["scores"].keys())
        for key in all_keys:
            case_aggregate[key] = sum(score["scores"].get(key, 0.0) for score in case_scores) / len(case_scores)
        per_case_scores.append((case["id"], case_aggregate))
        scores.append(case_scores)

    return aggregate(scores), per_case_scores

@pytest_asyncio.fixture
def load_eval_cases(base_dir="tests/prompts/datasets/local/municipal_officials"):
    base = pathlib.Path(base_dir)
    cases = []

    for case_dir in sorted(base.iterdir()):
        print(f"Loading case from {case_dir}")
        if not case_dir.is_dir():
            continue

        input_path = case_dir / "input.md"
        expected_path = case_dir / "expected.yml"

        if not input_path.exists() or not expected_path.exists():
            raise ValueError(f"Missing input.txt or expected.yml in {case_dir}")

        with open(expected_path, 'r', encoding='utf-8') as f:
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
    elif request.param == "together_ai":
        return {
            "name": "together_ai",
            "run_prompt": run_together_prompt,
            "make_prompt": make_together_prompt,
        }
    else:
        raise ValueError(f"Unknown model client: {request.param}")

# @pytest.mark.parametrize("model_client", ["gemini", "together_ai"], indirect=True)
@pytest.mark.parametrize("model_client", ["together_ai"], indirect=True)
@pytest.mark.asyncio
async def test_eval_with_mocked_cases(model_client, load_eval_cases):
    report, per_case_scores = await run_eval(model_client, load_eval_cases)
    print("Final aggregated report:", report)

    thresholds = {
        "name": 0.80,
        "roles": 0.90,
        "designations": 0.85,
        "email": 0.80,
        "phone": 0.80,
        "url": 0.0,
    }

    failed_cases = []
    for idx, (case_id, case_aggregate) in enumerate(per_case_scores):
        failed = []
        # Load the actual and expected people for this case
        # You need to reload the actual/expected people to get the details for reporting
        case = next(c for c in load_eval_cases if c["id"] == case_id)
        expected_people = [RawLLMPerson(**person) for person in case["expected"]["people"]]
        actual_path = os.path.join(case["case_path"], f"{model_client['name']}-actual.yml")
        if os.path.exists(actual_path):
            with open(actual_path, "r", encoding="utf-8") as f:
                actual_people = yaml.safe_load(f).get("people", [])
        else:
            actual_people = []

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
                if (actual_val is None or actual_val == "") and (expected_val is None or expected_val == ""):
                    score = 1.0
                elif key == "name":
                    score = 1.0 if norm_name == name_utils.normalize_name(actual_val) else 0.0
                elif key == "roles":
                    actual_roles = utils.people_utils.normalize_roles(a_person.get("roles", []))
                    expected_roles = utils.people_utils.normalize_roles(getattr(e_person, "roles", []))
                    matching_roles = set(actual_roles) & set(expected_roles)
                    score = len(matching_roles) / len(expected_roles) if expected_roles else 1.0
                elif key == "designations":
                    actual_designations = a_person.get("designations", [])
                    expected_designations = getattr(e_person, "designations", [])
                    has_district_or_ward = any(d in ["district", "ward"] for d in expected_designations)
                    if not expected_designations or not has_district_or_ward:
                        score = 1.0
                    else:
                        score = len(set(actual_designations) & set(expected_designations)) / len(expected_designations)
                elif key == "email":

                    score = 1.0 if actual_val == expected_val else 0.0
                elif key == "phone":
                    try:
                        actual_phone_parsed = phonenumbers.parse(actual_val, "US") if actual_val else None
                        expected_phone_parsed = phonenumbers.parse(expected_val, "US") if expected_val else None
                        score = 1.0 if actual_phone_parsed == expected_phone_parsed else 0.0
                    except Exception:
                        score = 0.0
                elif key == "url":
                    score = 1.0 if actual_val == expected_val else 0.0
                else:
                    score = 0.0

                if score < threshold:
                    failed.append({
                        "person": e_person.name,
                        "field": key,
                        "expected": expected_val,
                        "actual": actual_val,
                    })

        if failed:
            failed_cases.append({
                "model_client": model_client["name"],
                "case_number": idx,
                "case_id": case_id,
                "failures": failed
            })

    aggregate_failures = []
    aggregate_failed_cases = {}

    for field, threshold in thresholds.items():
        actual_score = report.get(field, 0.0)
        if actual_score < threshold:
            aggregate_failures.append({
                "field": field,
                "actual": actual_score,
                "threshold": threshold
            })
            # Collect all failed field instances across all cases
            field_failures = []
            for idx, (case_id, case_aggregate) in enumerate(per_case_scores):
                # Reload expected and actual people for this case
                case = next(c for c in load_eval_cases if c["id"] == case_id)
                expected_people = [RawLLMPerson(**person) for person in case["expected"]["people"]]
                actual_path = os.path.join(case["case_path"], f"{model_client['name']}-actual.yml")
                if os.path.exists(actual_path):
                    with open(actual_path, "r", encoding="utf-8") as f:
                        actual_people = yaml.safe_load(f).get("people", [])
                else:
                    actual_people = []
                actual_by_norm_name = {
                    name_utils.normalize_name(a.get("name", "")): a for a in actual_people
                }
                for e_person in expected_people:
                    norm_name = name_utils.normalize_name(e_person.name)
                    a_person = actual_by_norm_name.get(norm_name, {})
                    actual_val = a_person.get(field, "") if a_person else ""
                    expected_val = getattr(e_person, field, "")
                    # Treat null and '' as equal
                    if (actual_val is None or actual_val == "") and (expected_val is None or expected_val == ""):
                        score = 1.0
                    elif field == "name":
                        score = 1.0 if norm_name == name_utils.normalize_name(actual_val) else 0.0
                    elif field == "roles":
                        actual_roles = utils.people_utils.normalize_roles(a_person.get("roles", []))
                        expected_roles = utils.people_utils.normalize_roles(getattr(e_person, "roles", []))
                        matching_roles = set(actual_roles) & set(expected_roles)
                        score = len(matching_roles) / len(expected_roles) if expected_roles else 1.0
                    elif field == "designations":
                        actual_designations = a_person.get("designations", [])
                        expected_designations = getattr(e_person, "designations", [])
                        has_district_or_ward = any(d in ["district", "ward"] for d in expected_designations)
                        if not expected_designations or not has_district_or_ward:
                            score = 1.0
                        else:
                            score = len(set(actual_designations) & set(expected_designations)) / len(expected_designations)
                    elif field == "email":
                        score = 1.0 if actual_val == expected_val else 0.0
                    elif field == "phone":
                        try:
                            actual_phone_parsed = phonenumbers.parse(actual_val, "US") if actual_val else None
                            expected_phone_parsed = phonenumbers.parse(expected_val, "US") if expected_val else None
                            score = 1.0 if actual_phone_parsed == expected_phone_parsed else 0.0
                        except Exception:
                            score = 0.0
                    elif field == "url":
                        score = 1.0 if actual_val == expected_val else 0.0
                    else:
                        score = 0.0

                    if score < threshold:
                        field_failures.append({
                            "case_id": case_id,
                            "person": e_person.name,
                            "expected": expected_val,
                            "actual": actual_val
                        })
            aggregate_failed_cases[field] = field_failures

    # Write full report to file
    evals_dir = "tests/prompts/tests/evals/municipal_officials"
    os.makedirs(evals_dir, exist_ok=True)
    report_path = os.path.join(evals_dir, f"{model_client['name']}-eval-report.yml")
    with open(report_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({
            "aggregated_report": report,
            "aggregate_failures": aggregate_failures,
            "aggregate_failed_cases": aggregate_failed_cases,
            "per_case_scores": [
                {"case_id": case_id, "scores": case_aggregate}
                for case_id, case_aggregate in per_case_scores
            ],
            "failed_cases": failed_cases
        }, f, sort_keys=False)
    print(f"Saved evaluation report to {report_path}")

    # Assert thresholds
    assert report["name"] >= thresholds["name"]
    assert report["roles"] >= thresholds["roles"]
    assert report["designations"] >= thresholds["designations"]
    assert report["email"] >= thresholds["email"]
    assert report["phone"] >= thresholds["phone"]
    assert report["url"] >= thresholds["url"]
