"""EXTRACT on its own: the questions it asks, how often, and when it stops. The model is faked
per question; what it answers is 2.13's eval's business, not this file's."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runners.pipeline02_organizations_collector.role_asks import RoleAsk
from runners.pipeline02_organizations_collector.schemas import (
    FilledBy,
    OrganizationsCollectorConfig,
    OrganizationsCollectorContext,
    OrganizationsCollectorData,
    OrganizationsCollectorStep,
    RoleAnswer,
    RoleClaim,
)
from runners.pipeline02_organizations_collector.transitions.main import ASKS_PER_QUESTION, extract
from shared.schemas import PipelineRunLimits
from shared.utils.layered_config import ConfigFile, merged_config

pytestmark = pytest.mark.unit

MAIN = "runners.pipeline02_organizations_collector.transitions.main"
_LAW = "# Charter\n\n- **§ 1. Selectboard**\nThe Selectboard shall consist of five members elected at large.\n"
_MEMBER = RoleAsk(organization_name="Select Board", role_id="member", role_label="Select Board Member", names=["Select Board Member"])
_CHAIR = RoleAsk(organization_name="Select Board", role_id="chair", role_label="Chair", names=["Chair"])
_ANSWER = {"established": True, "label": "Selectboard member", "filled_by": "elected_by_voters", "maximum_memberships": 5, "quote": "five members elected at large"}


def _context(pending: list[RoleAsk], claims: list[RoleClaim] | None = None) -> OrganizationsCollectorContext:
    return OrganizationsCollectorContext(
        pipeline_run_id="run-1",
        current_state=OrganizationsCollectorStep.EXTRACT,
        data=OrganizationsCollectorData(
            jurisdiction_ocdid="ocd-jurisdiction/country:us/state:vt/place:stowe/government",
            config=OrganizationsCollectorConfig(
                name="Stowe town", governing_law=None, jurisdiction_config=merged_config(ConfigFile(), ConfigFile(), None), government_form=None
            ),
            selected_governing_law_text=_LAW,
            pending_asks=pending,
            claims=claims or [],
        ),
    )


def _limits(cap: str) -> PipelineRunLimits:
    return MagicMock(spec=PipelineRunLimits, pipeline_run_cap_usd=Decimal(cap))


async def _extract(context: OrganizationsCollectorContext, spent: str = "0", cap: str = "1"):
    async def answer(*_args, prompt_name: str, **_kwargs):
        return {"offices": [{"label": "Town Clerk", "filled_by": "appointed", "quote": "shall appoint a Town Clerk"}]} if prompt_name == "governing_other_offices" else _ANSWER

    model = AsyncMock(side_effect=answer)
    with patch(f"{MAIN}.open_router_llm.run_prompt", new=model), patch(f"{MAIN}.cost_utils.total_cost", return_value=Decimal(spent)):
        extracted, next_state = await extract(_limits(cap), MagicMock(), context, MagicMock())
    return extracted, next_state, model


def _prompt_names(model: AsyncMock) -> list[str]:
    return [call.kwargs["prompt_name"] for call in model.call_args_list]


@pytest.mark.asyncio
async def test_each_role_is_asked_twice():
    extracted, next_state, model = await _extract(_context([_MEMBER, _CHAIR]))

    assert _prompt_names(model).count("governing_role") == 2 * ASKS_PER_QUESTION
    assert [claim.ask.role_id for claim in extracted.data.claims] == ["member", "member", "chair", "chair"]
    assert next_state == OrganizationsCollectorStep.VERIFY


@pytest.mark.asyncio
async def test_the_answer_is_kept_with_its_question():
    extracted, _, _ = await _extract(_context([_MEMBER]))

    assert extracted.data.claims[0] == RoleClaim(ask=_MEMBER, answer=RoleAnswer.model_validate(_ANSWER))
    assert extracted.data.pending_asks == []


@pytest.mark.asyncio
async def test_the_question_comes_after_the_law():
    _, _, model = await _extract(_context([_MEMBER]))

    content = model.call_args_list[0].kwargs["content"]
    assert content.startswith(_LAW)
    assert "Select Board Member" in content[len(_LAW):]


@pytest.mark.asyncio
async def test_the_first_pass_also_asks_for_offices_nobody_asked_about():
    extracted, _, model = await _extract(_context([_MEMBER]))

    assert _prompt_names(model).count("governing_other_offices") == 1
    assert [office.label for office in extracted.data.other_offices] == ["Town Clerk"]


@pytest.mark.asyncio
async def test_a_re_ask_does_not_ask_for_other_offices_again():
    earlier = RoleClaim(ask=_CHAIR, answer=RoleAnswer.model_validate({**_ANSWER, "filled_by": FilledBy.NOT_STATED}))

    _, _, model = await _extract(_context([_MEMBER], claims=[earlier]))

    assert "governing_other_offices" not in _prompt_names(model)


@pytest.mark.asyncio
async def test_nothing_is_asked_once_the_cap_is_spent():
    extracted, next_state, model = await _extract(_context([_MEMBER]), spent="1", cap="1")

    model.assert_not_called()
    assert extracted.data.stopped_at_cost_cap
    assert extracted.data.pending_asks == []
    assert next_state == OrganizationsCollectorStep.VERIFY


@pytest.mark.asyncio
async def test_a_question_that_fails_leaves_its_role_unanswered_not_the_run_ended():
    async def answer(*_args, prompt_name: str, content: str, **_kwargs):
        if prompt_name == "governing_role" and "Chair" in content[len(_LAW):]:
            raise ValueError("OpenRouter response missing 'choices'")
        return {"offices": []} if prompt_name == "governing_other_offices" else _ANSWER

    with patch(f"{MAIN}.open_router_llm.run_prompt", new=AsyncMock(side_effect=answer)), patch(
        f"{MAIN}.cost_utils.total_cost", return_value=Decimal("0")
    ):
        extracted, next_state = await extract(_limits("1"), MagicMock(), _context([_MEMBER, _CHAIR]), MagicMock())

    assert [claim.ask.role_id for claim in extracted.data.claims] == ["member", "member"]
    assert next_state == OrganizationsCollectorStep.VERIFY
