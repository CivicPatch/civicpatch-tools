"""The words layer on a sample of Vermont's prod organization labels: it never places anyone wrong,
and it answers no smaller share of them than it does today. Raise the floor when a change answers more."""

import pathlib

import pytest
import yaml
from accuracy import build_eval_taxonomy

from runners.pipeline03_people_collector.steps.step_04_process_page_content.organization_match import (
    match_by_words,
    place_words,
    with_role_aliases,
)
from shared.schemas import KnownOrganization, SelectionMethod
from shared.utils.taxonomy import with_selection_methods

pytestmark = pytest.mark.unit

CASES = pathlib.Path(__file__).parents[2] / "prompts/datasets/local/organization_match/vermont_prod.yml"
NONE = "none"
# The eval's taxonomy fixture lists roles but not how they are filled; these, as open-data's roles say.
_FILLED_BY_MEMBERS = ["chair", "vice-chair", "vice-mayor", "mayor-pro-tem", "president-pro-tem", "council-president"]
# The share answered right today; a change must not lower it.
RIGHT_SHARE_FLOOR = 0.844


def _answers() -> list[tuple[str, str, str]]:
    data = yaml.safe_load(CASES.read_text())
    taxonomy = with_selection_methods(
        build_eval_taxonomy(), {role_id: SelectionMethod.ELECTED_BY_MEMBERS for role_id in _FILLED_BY_MEMBERS}
    )
    organizations_by_place = {
        slug: with_role_aliases(
            [KnownOrganization(id=entry["name"], **entry) for entry in data["organization_sets"][place["organizations"]]], taxonomy
        )
        for slug, place in data["places"].items()
    }
    answers = []
    for case in data["cases"]:
        place = data["places"][case["place"]]
        match = match_by_words(case["organization_label"], place_words(organizations_by_place[case["place"]], taxonomy, place["name"]))
        answers.append((case["organization_label"], match.names[0] if len(match.names) == 1 else NONE, case["expected"]))
    return answers


def test_the_words_never_place_a_vermont_label_wrong():
    wrong = [(label, got, expected) for label, got, expected in _answers() if got != NONE and got != expected]

    assert wrong == []


def test_the_words_answer_at_least_as_large_a_share_of_vermont_labels_as_before():
    answers = _answers()
    share = sum(got == expected for _, got, expected in answers) / len(answers)

    assert share >= RIGHT_SHARE_FLOOR, f"{share:.3f} right, floor {RIGHT_SHARE_FLOOR}"
