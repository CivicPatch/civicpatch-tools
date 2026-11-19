"""The placement rules on Vermont prod's person records: the person's own label and the page's organization
label together. Wrong placements may only fall, the right share only rise, and no more
records may be left to the models; tighten the numbers when a change does better."""

import pathlib

import pytest
import yaml

from runners.pipeline03_people_collector.steps.step_02_crawl_page.step_02c_process_page_content.organization_match import (
    place_words,
    with_role_aliases,
)
from runners.pipeline03_people_collector.steps.step_02_crawl_page.step_02c_process_page_content.person_placement import (
    placed_by_rules,
)
from shared.schemas import KnownOrganization, Role, RoleConfig
from shared.utils.taxonomy import build_taxonomy

pytestmark = pytest.mark.unit

CASES = pathlib.Path(__file__).parents[2] / "prompts/datasets/local/organization_match/vermont_people.yml"
# Today's counts; a change must not raise the first or third or lower the second.
WRONG_CEILING = 11
RIGHT_SHARE_FLOOR = 0.815
LEFT_TO_THE_MODELS_CEILING = 33


class Answer:
    def __init__(self, case: dict, settled: bool, placed: str | None, right: bool):
        self.case, self.settled, self.placed, self.right = case, settled, placed, right

    def __repr__(self) -> str:
        return f"{self.case['place']}: {self.case['organization_label']!r} / {self.case['label']!r} -> {self.placed} (expected {self.case['expected']})"


def _answers() -> list[Answer]:
    data = yaml.safe_load(CASES.read_text())
    taxonomy = build_taxonomy(RoleConfig(roles=[Role(**role) for role in data["roles"]]))
    organizations_by_set = {
        key: with_role_aliases([KnownOrganization(id=entry["name"], **entry) for entry in entries], taxonomy)
        for key, entries in data["organization_sets"].items()
    }
    answers = []
    for case in data["cases"]:
        place = data["places"][case["place"]]
        organizations = organizations_by_set[place["organizations"]]
        default = next(known.name for known in organizations if known.meta_is_default)
        placement = placed_by_rules(case["organization_label"], case["label"], place_words(organizations, taxonomy, place["name"]), taxonomy)
        # None leaves the record to ingest, which keeps it in the default organization.
        right = placement.settled and (placement.name or default) == case["expected"]
        answers.append(Answer(case, placement.settled, placement.name, right))
    return answers


def test_the_rules_place_no_more_vermont_people_wrong_than_before():
    wrong = [answer for answer in _answers() if answer.settled and not answer.right]

    assert len(wrong) <= WRONG_CEILING, "\n".join(map(repr, wrong))


def test_the_rules_place_at_least_as_large_a_share_of_vermont_people_right_as_before():
    answers = _answers()
    share = sum(answer.right for answer in answers) / len(answers)

    assert share >= RIGHT_SHARE_FLOOR, f"{share:.3f} right, floor {RIGHT_SHARE_FLOOR}"


def test_the_rules_leave_no_more_vermont_people_to_the_models_than_before():
    left = [answer for answer in _answers() if not answer.settled]

    assert len(left) <= LEFT_TO_THE_MODELS_CEILING, f"{len(left)} left to the models"
