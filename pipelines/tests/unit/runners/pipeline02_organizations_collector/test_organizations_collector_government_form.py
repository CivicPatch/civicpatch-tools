"""What pipeline 2 reads back from the model's form answer, and INIT asking it first. Whether to ask is cp.org's call."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runners.pipeline02_organizations_collector.government_form import answered_government_form
from runners.pipeline02_organizations_collector.schemas import (
    OrganizationsCollectorConfig,
    OrganizationsCollectorContext,
    OrganizationsCollectorData,
    OrganizationsCollectorStep,
)
from runners.pipeline02_organizations_collector.transitions.main import start
from shared.schemas import GovernmentForm
from shared.utils.layered_config import ConfigFile, merged_config
from shared.utils.statuses import PipelineRunStatus

pytestmark = pytest.mark.unit

_TWO = [GovernmentForm.MAYOR_COUNCIL, GovernmentForm.COUNCIL_MANAGER]


def test_an_answer_counts_only_if_it_was_offered():
    assert answered_government_form({"government_form": "council_manager"}, _TWO) == GovernmentForm.COUNCIL_MANAGER
    assert answered_government_form({"government_form": "open_town_meeting"}, _TWO) is None
    assert answered_government_form({}, _TWO) is None


_TOWN_FORMS = [GovernmentForm.COUNCIL_MANAGER, GovernmentForm.OPEN_TOWN_MEETING]
_GOVERNMENT_FORM = "runners.pipeline02_organizations_collector.government_form"


def _context(choices: list[GovernmentForm]) -> OrganizationsCollectorContext:
    return OrganizationsCollectorContext(
        pipeline_run_id="run-1",
        current_state=PipelineRunStatus.INIT,
        data=OrganizationsCollectorData(
            jurisdiction_ocdid="ocd-jurisdiction/country:us/state:me/place:wayne/government",
            config=OrganizationsCollectorConfig(
                name="Wayne town",
                governing_law=None,
                jurisdiction_config=merged_config(ConfigFile(), ConfigFile()),
                government_form=None,
                government_form_choices=choices,
            ),
        ),
    )


async def _start(choices: list[GovernmentForm], answer: dict | None):
    with (
        patch(f"{_GOVERNMENT_FORM}.google_gemini_llm.run_prompt", new=AsyncMock(return_value=answer)) as ask,
        patch(f"{_GOVERNMENT_FORM}.civicpatch_api.patch_jurisdiction_extras", new=AsyncMock()) as save,
    ):
        next_context, next_state = await start(MagicMock(), MagicMock(), _context(choices), AsyncMock())
    assert next_state == OrganizationsCollectorStep.SELECT_SECTIONS
    return next_context, ask, save


@pytest.mark.asyncio
async def test_init_asks_the_form_and_runs_with_the_one_it_saved():
    next_context, _, save = await _start(_TOWN_FORMS, {"government_form": "open_town_meeting"})

    assert next_context.data.config.government_form == GovernmentForm.OPEN_TOWN_MEETING
    save.assert_awaited_once()


@pytest.mark.asyncio
async def test_init_with_no_choices_asks_nothing():
    next_context, ask, _ = await _start([], None)

    ask.assert_not_awaited()
    assert next_context.data.config.government_form is None


@pytest.mark.asyncio
async def test_an_answer_naming_no_offered_form_leaves_every_form_and_saves_nothing():
    next_context, _, save = await _start(_TOWN_FORMS, {"government_form": "commission"})

    save.assert_not_awaited()
    assert next_context.data.config.government_form is None
