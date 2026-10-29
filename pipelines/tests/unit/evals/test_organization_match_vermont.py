"""The words layer on a sample of Vermont's prod organization labels: it never places anyone wrong,
and it answers no smaller share of them than it does today. Raise the floor when a change answers more."""

import pathlib

import pytest
import yaml
from accuracy import build_eval_taxonomy

from runners.pipeline03_people_collector.steps.step_04_process_page_content.organization_match import (
    match_by_words,
    with_role_aliases,
)
from shared.schemas import KnownOrganization

pytestmark = pytest.mark.unit

CASES = pathlib.Path(__file__).parents[2] / "prompts/datasets/local/organization_match/vermont_prod.yml"
NONE = "none"
# The share answered right today; a change must not lower it.
RIGHT_SHARE_FLOOR = 0.836


def _answers() -> list[tuple[str, str, str]]:
    data = yaml.safe_load(CASES.read_text())
    taxonomy = build_eval_taxonomy()
    organizations_by_place = {
        slug: with_role_aliases(
            [KnownOrganization(id=entry["name"], **entry) for entry in data["organization_sets"][place["organizations"]]], taxonomy
        )
        for slug, place in data["places"].items()
    }
    answers = []
    for case in data["cases"]:
        place = data["places"][case["place"]]
        match = match_by_words(case["organization_label"], place["name"], organizations_by_place[case["place"]])
        answers.append((case["organization_label"], match.names[0] if len(match.names) == 1 else NONE, case["expected"]))
    return answers


def test_the_words_never_place_a_vermont_label_wrong():
    wrong = [(label, got, expected) for label, got, expected in _answers() if got != NONE and got != expected]

    assert wrong == []


def test_the_words_answer_at_least_as_large_a_share_of_vermont_labels_as_before():
    answers = _answers()
    share = sum(got == expected for _, got, expected in answers) / len(answers)

    assert share >= RIGHT_SHARE_FLOOR, f"{share:.3f} right, floor {RIGHT_SHARE_FLOOR}"
