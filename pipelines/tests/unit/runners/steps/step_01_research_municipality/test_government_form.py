"""Pure — what research reads back from the model's form answer. Whether to ask is cp.org's call."""

import pytest

from runners.pipeline03_people_collector.steps.step_01_research_municipality.government_form import answered_government_form
from shared.schemas import GovernmentForm

pytestmark = pytest.mark.unit

_TWO = [GovernmentForm.MAYOR_COUNCIL, GovernmentForm.COUNCIL_MANAGER]


def test_an_answer_counts_only_if_it_was_offered():
    assert answered_government_form({"government_form": "council_manager"}, _TWO) == GovernmentForm.COUNCIL_MANAGER
    assert answered_government_form({"government_form": "open_town_meeting"}, _TWO) is None
    assert answered_government_form({}, _TWO) is None
