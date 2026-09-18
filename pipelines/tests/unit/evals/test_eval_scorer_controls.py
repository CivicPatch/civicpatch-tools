import pathlib
import re

import pytest
import yaml
from accuracy import (
    GATE_THRESHOLDS,
    case_dispositions,
    case_mismatches,
    merge_dispositions,
    summarize,
)
from scoring import (
    EVAL_TAXONOMY,
    aggregate_case,
    case_score,
    person_precision,
    score_cases,
)
from test_local_municipal_officials_eval import make_together_prompt
from test_local_relevant_page_eval import page_dispositions, score_page

from runners.people_collector.schemas import ExtractedPersonRecord
from shared.utils.label_parser import parse_label
from tests.factories.extracted_person import extracted_person_factory

pytestmark = pytest.mark.unit

DATASETS = pathlib.Path(__file__).resolve().parents[2] / "prompts" / "datasets" / "local"


def _case_dirs(eval_dir_name):
    return sorted(path for path in (DATASETS / eval_dir_name).iterdir() if path.is_dir())


def _expected(case_dir):
    return yaml.safe_load((case_dir / "expected.yml").read_text(encoding="utf-8"))


def _cases_where(case_dirs, predicate):
    return [case_dir for case_dir in case_dirs if predicate(_expected(case_dir)["people"])]


OFFICIALS_CASES = _case_dirs("municipal_officials")
RELEVANT_PAGE_CASES = _case_dirs("relevant_page")
CASES_WITH_PEOPLE = _cases_where(OFFICIALS_CASES, lambda people: len(people) > 0)
CASES_WITH_SEVERAL_PEOPLE = _cases_where(OFFICIALS_CASES, lambda people: len(people) > 1)
CASES_WITH_PHONES = _cases_where(OFFICIALS_CASES, lambda people: any(p.get("phone") for p in people))
CASES_WITH_EMAILS = _cases_where(OFFICIALS_CASES, lambda people: any(p.get("email") for p in people))
# Valid under the phone normalizer, so a changed number is a wrong value, not a missing one.
CHANGED_PHONE = "(212) 555-0100"
CHANGED_EMAIL = "changed@example.com"
QUOTED = re.compile(r'"([^"\n]+)"')
PHONE_PATTERN = re.compile(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")



def _expected_people(case_dir):
    return [ExtractedPersonRecord(**person) for person in _expected(case_dir)["people"]]


def _summary(actual, expected):
    return summarize(merge_dispositions([case_dispositions(actual, expected, EVAL_TAXONOMY)]))


def _failed_gates(actual, expected):
    summary = _summary(actual, expected)
    return [
        field
        for field, floor in GATE_THRESHOLDS.items()
        if floor and summary[field].f1 is not None and summary[field].f1 < floor
    ]


def _imperfect_dispositions(dispositions):
    return {
        field: [d.value for d in found if d.value != "correct"]
        for field, found in dispositions.items()
        if any(d.value != "correct" for d in found)
    }


@pytest.mark.parametrize("case_dir", OFFICIALS_CASES, ids=lambda path: path.name)
def test_officials_expected_scores_perfectly_against_itself(case_dir):
    people = _expected_people(case_dir)
    imperfect = [
        (person["person_name"], field, score)
        for person in score_cases(people, people)
        for field, score in person["scores"].items()
        if score != 1.0
    ]
    assert imperfect == []


@pytest.mark.parametrize("case_dir", OFFICIALS_CASES, ids=lambda path: path.name)
def test_officials_expected_has_only_correct_dispositions_against_itself(case_dir):
    people = _expected_people(case_dir)
    assert _imperfect_dispositions(case_dispositions(people, people, EVAL_TAXONOMY)) == {}


@pytest.mark.parametrize("case_dir", OFFICIALS_CASES, ids=lambda path: path.name)
def test_officials_expected_has_no_mismatches_against_itself(case_dir):
    people = _expected_people(case_dir)
    assert case_mismatches(people, people, EVAL_TAXONOMY) == []


@pytest.mark.parametrize("case_dir", RELEVANT_PAGE_CASES, ids=lambda path: path.name)
def test_relevant_page_expected_scores_perfectly_against_itself(case_dir):
    page = _expected(case_dir)["page"]
    assert score_page(page, page) == {"is_relevant": 1.0, "relevant_urls": 1.0}


@pytest.mark.parametrize("case_dir", RELEVANT_PAGE_CASES, ids=lambda path: path.name)
def test_relevant_page_expected_has_only_correct_dispositions_against_itself(case_dir):
    page = _expected(case_dir)["page"]
    assert _imperfect_dispositions(page_dispositions(page, page)) == {}


@pytest.mark.parametrize("case_dir", CASES_WITH_PEOPLE, ids=lambda path: path.name)
def test_returning_nobody_fails_the_person_gate(case_dir):
    people = _expected_people(case_dir)
    assert _summary([], people)["person"].f1 == 0.0
    assert "person" in _failed_gates([], people)


@pytest.mark.parametrize("case_dir", CASES_WITH_PEOPLE, ids=lambda path: path.name)
def test_inventing_as_many_people_again_fails_the_person_gate(case_dir):
    people = _expected_people(case_dir)
    invented = [extracted_person_factory(f"Invented Person {i}", people[0].label) for i in range(len(people))]
    assert "person" in _failed_gates(people + invented, people)


@pytest.mark.parametrize("case_dir", CASES_WITH_PEOPLE, ids=lambda path: path.name)
def test_inventing_as_many_people_again_halves_the_case_score(case_dir):
    people = _expected_people(case_dir)
    padded = people + [extracted_person_factory(f"Invented Person {i}", people[0].label) for i in range(len(people))]
    assert case_score(aggregate_case(score_cases(padded, people)), person_precision(padded, people)) <= 0.5


@pytest.mark.parametrize("case_dir", CASES_WITH_SEVERAL_PEOPLE, ids=lambda path: path.name)
def test_rotating_names_between_seats_fails_a_gate(case_dir):
    people = _expected_people(case_dir)
    names = [person.name for person in people]
    rotated = [person.model_copy(update={"name": names[(i + 1) % len(names)]}) for i, person in enumerate(people)]
    assert _failed_gates(rotated, people) != []


@pytest.mark.parametrize("case_dir", CASES_WITH_PHONES, ids=lambda path: path.name)
def test_changing_every_phone_scores_phone_zero(case_dir):
    people = _expected_people(case_dir)
    changed = [p.model_copy(update={"phone": CHANGED_PHONE if p.phone else None}) for p in people]
    assert _summary(changed, people)["phone"].f1 == 0.0


@pytest.mark.parametrize("case_dir", CASES_WITH_EMAILS, ids=lambda path: path.name)
def test_changing_every_email_scores_email_zero(case_dir):
    people = _expected_people(case_dir)
    changed = [p.model_copy(update={"email": CHANGED_EMAIL if p.email else None}) for p in people]
    assert _summary(changed, people)["email"].f1 == 0.0


def test_people_returned_when_nobody_was_expected_fail_the_person_gate():
    invented = [extracted_person_factory(name, "Council Member") for name in ("Ann Invented", "Bo Invented", "Cy Invented")]
    assert _summary(invented, [])["person"].f1 == 0.0
    assert "person" in _failed_gates(invented, [])


def test_extra_roles_cost_precision():
    expected = [extracted_person_factory("Kirk Watson", "Mayor")]
    actual = [extracted_person_factory("Kirk Watson", "Mayor and Council Member")]
    # `roles` is recall over expected, so the extra role is only visible as precision.
    [person] = score_cases(actual, expected)
    assert person["scores"]["roles_precision"] < 1.0
    assert _summary(actual, expected)["roles"].false_positive == 1


def test_an_invented_start_date_is_a_false_positive():
    summary = _summary([extracted_person_factory("Kirk Watson", "Mayor", start_date="2025-01")], [extracted_person_factory("Kirk Watson", "Mayor")])
    assert summary["start_date"].false_positive == 1


def test_an_invented_phone_scores_zero():
    expected = [extracted_person_factory("Kirk Watson", "Mayor")]
    actual = [extracted_person_factory("Kirk Watson", "Mayor", phone=CHANGED_PHONE)]
    [person] = score_cases(actual, expected)
    assert person["scores"]["phone"] == 0.0
    assert _summary(actual, expected)["phone"].false_positive == 1


def test_a_different_name_is_not_matched_to_the_expected_person():
    summary = _summary([extracted_person_factory("Kirk Watts", "Mayor")], [extracted_person_factory("Kirk Watson", "Mayor")])
    assert (summary["person"].correct, summary["person"].false_negative, summary["person"].false_positive) == (0, 1, 1)


def test_an_extra_url_is_not_counted_against_a_provider():
    """A fixture lists the links that must be followed, not every link that may be.

    Changed 2026-09-18 from counting extras as false positives. On the Jackson case a provider
    returned `/government` (a hub), `meetthecouncil` (a roster) and `aboutmayorconger` (the
    mayor's own page), all three exactly what the prompt asks for and none of them in an expected
    list of two. Scoring them as errors measured the fixture rather than the model.
    """
    expected = {"is_relevant": True, "relevant_urls": ["https://a.gov/council"]}
    actual = {"is_relevant": True, "relevant_urls": ["https://a.gov/council", "https://a.gov/news", "https://a.gov/parks"]}
    found = [d.value for d in page_dispositions(actual, expected)["relevant_urls"]]
    assert found == ["correct"]


def test_a_missing_url_is_still_counted():
    """The asymmetry that justifies the leniency: an extra link costs one fetch, a missing one
    costs a page the crawler can never reach."""
    expected = {"is_relevant": True, "relevant_urls": ["https://a.gov/council", "https://a.gov/mayor"]}
    actual = {"is_relevant": True, "relevant_urls": ["https://a.gov/council"]}
    found = [d.value for d in page_dispositions(actual, expected)["relevant_urls"]]
    assert found == ["correct", "false_negative"]


def test_urls_returned_when_none_were_expected_are_not_penalised():
    expected = {"is_relevant": False, "relevant_urls": []}
    actual = {"is_relevant": False, "relevant_urls": ["https://a.gov/news", "https://a.gov/parks"]}
    found = [d.value for d in page_dispositions(actual, expected)["relevant_urls"]]
    assert found == []


def _last_ten_digits(phone):
    return re.sub(r"\D", "", phone)[-10:]


def _appears_in(value, prompt):
    return re.search(rf"(?<!\w){re.escape(value)}(?!\w)", prompt, re.IGNORECASE) is not None


def _label_parts(label):
    parsed = parse_label(label, EVAL_TAXONOMY)
    division = (parsed.division.designation, parsed.division.value) if parsed.division else None
    return tuple(sorted(parsed.roles)), division, tuple(sorted(parsed.other_designations))


def _names_a_specific_seat(parts):
    # "District 1" exists on nearly every council; a named seat like "East Ward" is one place's answer.
    _, division, _ = parts
    return division is not None and not division[1].isdigit()


def _prompt_seat_labels(prompt):
    return {parts for parts in map(_label_parts, QUOTED.findall(prompt)) if _names_a_specific_seat(parts)}


def _leaked_values(people, prompt):
    prompt_phones = {_last_ten_digits(match) for match in PHONE_PATTERN.findall(prompt)}
    prompt_labels = _prompt_seat_labels(prompt)
    leaks = []
    for person in people:
        if _appears_in(person["name"], prompt):
            leaks.append(("name", person["name"]))
        if person.get("label") and _label_parts(person["label"]) in prompt_labels:
            leaks.append(("label", person["label"]))
        if person.get("phone") and _last_ten_digits(person["phone"]) in prompt_phones:
            leaks.append(("phone", person["phone"]))
        if person.get("email") and person["email"].lower() in prompt.lower():
            leaks.append(("email", person["email"]))
    return leaks


@pytest.mark.parametrize("case_dir", CASES_WITH_PEOPLE, ids=lambda path: path.name)
def test_officials_prompt_does_not_contain_expected_people(case_dir):
    expected = _expected(case_dir)
    prompt = make_together_prompt(expected)
    assert _leaked_values(expected["people"], prompt) == []


def test_leak_check_finds_a_planted_name_label_phone_and_email():
    people = [{
        "name": "Kirk Watson",
        "label": "Council Member Place 3 (East Ward)",
        "phone": "512-978-2100",
        "email": "kirk@austintexas.gov",
    }]
    prompt = 'Example: KIRK WATSON, "Place 3 (East Ward) Councilman", (512) 978-2100, Kirk@AustinTexas.gov'
    assert _leaked_values(people, prompt) == [
        ("name", "Kirk Watson"),
        ("label", "Council Member Place 3 (East Ward)"),
        ("phone", "512-978-2100"),
        ("email", "kirk@austintexas.gov"),
    ]


def test_leak_check_ignores_a_bare_title():
    assert _leaked_values([{"name": "Kirk Watson", "label": "Mayor"}], 'titles like "Mayor"') == []
