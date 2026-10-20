"""VERIFY's decision per role, over a small charter and the general law cached beside it."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from runners.organizations_collector.role_asks import RoleAsk
from runners.organizations_collector.schemas import (
    FilledBy,
    OrganizationsCollectorConfig,
    OrganizationsCollectorContext,
    OrganizationsCollectorData,
    OrganizationsCollectorStep,
    RoleAnswer,
    RoleClaim,
)
from runners.organizations_collector.sections import GoverningLawPage
from runners.organizations_collector.transitions.main import verify
from runners.organizations_collector.verify import MAX_ROUNDS, role_outcomes
from shared.schemas import FoundBy, GoverningLaw, GoverningLawKind, SelectionMethod
from shared.utils.layered_config import Classification, ConfigFile, GovernedBy, GoverningLawConfig, merged_config

pytestmark = pytest.mark.unit

_STATUTE_URL = "https://legislature.vermont.gov/statutes/section/24/033/00871"
_VERMONT = GoverningLawConfig(
    charter_terms=["charter"],
    classifications={"town": Classification(governed_by=GovernedBy.CHARTER_OR_GENERAL_LAW, general_law=[_STATUTE_URL])},
)
_CHARTER = GoverningLawPage(
    id="charter",
    source_url="https://legislature.vermont.gov/statutes/fullchapter/24APPENDIX/153",
    text="- **§ 401. Officers**\nThe Selectboard shall appoint a Town Clerk. The Selectboard shall consist of five members elected at large.\n",
)
_STATUTE = GoverningLawPage(
    id="statute",
    source_url=_STATUTE_URL,
    text="- **§ 871. Town officers**\nThe town clerk shall be elected at the annual meeting.\n",
)
_LAW = GoverningLaw(
    kind=GoverningLawKind.CHARTER,
    classification="town",
    found_by=FoundBy.STATE_INDEX,
    source_page_ids=["charter", "statute"],
    collected_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
    cost_usd=None,
)
_MEMBER = RoleAsk(organization_name="Select Board", role_id="member", role_label="Select Board Member", names=["Select Board Member", "selectboard member", "members"])
_CLERK = RoleAsk(organization_name="Select Board", role_id="clerk", role_label="Clerk", names=["Clerk", "Town Clerk"])


def _claim(ask: RoleAsk, quote: str, filled_by: FilledBy, established: bool = True) -> RoleClaim:
    answer = RoleAnswer(established=established, label=ask.role_label if established else "", filled_by=filled_by, maximum_memberships=None, quote=quote)
    return RoleClaim(ask=ask, answer=answer)


def _outcomes(claims: list[RoleClaim]):
    return role_outcomes(claims, [_CHARTER, _STATUTE], _LAW, _VERMONT, asks_per_question=2)


_FIVE_MEMBERS = "consist of five members elected at large"
_NOT_IN_THE_LAW = "seven members elected by district"


def test_one_verified_answer_of_two_verifies_the_role():
    outcomes = _outcomes([_claim(_MEMBER, _NOT_IN_THE_LAW, FilledBy.ELECTED_BY_VOTERS), _claim(_MEMBER, _FIVE_MEMBERS, FilledBy.ELECTED_BY_VOTERS)])

    [member] = outcomes.verified
    assert member.selection_method == SelectionMethod.ELECTED_BY_VOTERS
    assert (member.source_page_id, member.page_kind) == ("charter", GoverningLawKind.CHARTER)
    assert member.quote == "The Selectboard shall consist of five members elected at large."


def test_a_role_both_answers_say_is_not_established_is_not():
    outcomes = _outcomes([_claim(_MEMBER, "", FilledBy.NOT_STATED, established=False)] * 2)

    assert outcomes.not_established == [_MEMBER]


def test_a_role_with_nothing_verified_is_asked_again():
    outcomes = _outcomes([_claim(_MEMBER, _NOT_IN_THE_LAW, FilledBy.ELECTED_BY_VOTERS)] * 2)

    assert outcomes.re_ask == [_MEMBER]


def test_after_the_last_round_a_role_with_nothing_verified_is_left_unverified():
    outcomes = _outcomes([_claim(_MEMBER, _NOT_IN_THE_LAW, FilledBy.ELECTED_BY_VOTERS)] * 2 * MAX_ROUNDS)

    assert (outcomes.re_ask, outcomes.unverified) == ([], [_MEMBER])


def test_the_charter_wins_over_the_general_law():
    outcomes = _outcomes([
        _claim(_CLERK, "The town clerk shall be elected at the annual meeting", FilledBy.ELECTED_BY_VOTERS),
        _claim(_CLERK, "The Selectboard shall appoint a Town Clerk", FilledBy.APPOINTED),
    ])

    [clerk] = outcomes.verified
    assert (clerk.selection_method, clerk.source_page_id) == (SelectionMethod.APPOINTED, "charter")


def test_the_general_law_answers_where_the_charter_is_silent():
    outcomes = _outcomes([_claim(_CLERK, "The town clerk shall be elected at the annual meeting", FilledBy.ELECTED_BY_VOTERS)] * 2)

    [clerk] = outcomes.verified
    assert (clerk.source_page_id, clerk.page_kind) == ("statute", GoverningLawKind.GENERAL_LAW)


def test_a_stated_method_wins_over_not_stated():
    outcomes = _outcomes([
        _claim(_CLERK, "The Selectboard shall appoint a Town Clerk", FilledBy.NOT_STATED),
        _claim(_CLERK, "The Selectboard shall appoint a Town Clerk", FilledBy.APPOINTED),
    ])

    assert outcomes.verified[0].selection_method == SelectionMethod.APPOINTED


def test_two_methods_both_in_the_general_law_are_a_conflict():
    statute = _STATUTE.model_copy(update={"text": _STATUTE.text + "The selectboard shall appoint the town clerk.\n"})
    claims = [
        _claim(_CLERK, "The town clerk shall be elected at the annual meeting", FilledBy.ELECTED_BY_VOTERS),
        _claim(_CLERK, "The selectboard shall appoint the town clerk", FilledBy.APPOINTED),
    ]

    outcomes = role_outcomes(claims, [statute], _LAW, _VERMONT, asks_per_question=2)

    assert outcomes.conflicted == [_CLERK]


def _context(claims: list[RoleClaim], stopped_at_cost_cap: bool = False) -> OrganizationsCollectorContext:
    return OrganizationsCollectorContext(
        pipeline_run_id="run-1",
        current_state=OrganizationsCollectorStep.VERIFY,
        data=OrganizationsCollectorData(
            jurisdiction_ocdid="ocd-jurisdiction/country:us/state:vt/place:stowe/government",
            config=OrganizationsCollectorConfig(
                name="Stowe town",
                governing_law=_LAW,
                jurisdiction_config=merged_config(ConfigFile(), ConfigFile(), ConfigFile(governing_law=_VERMONT)),
                government_form=None,
            ),
            governing_law_pages=[_CHARTER, _STATUTE],
            claims=claims,
            stopped_at_cost_cap=stopped_at_cost_cap,
        ),
    )


@pytest.mark.asyncio
async def test_verify_sends_the_unverified_back_to_extract():
    verified, next_state = await verify(MagicMock(), MagicMock(), _context([_claim(_MEMBER, _NOT_IN_THE_LAW, FilledBy.ELECTED_BY_VOTERS)] * 2), MagicMock())

    assert next_state == OrganizationsCollectorStep.EXTRACT
    assert verified.data.pending_asks == [_MEMBER]


@pytest.mark.asyncio
async def test_verify_goes_to_write_once_every_role_is_decided():
    _, next_state = await verify(MagicMock(), MagicMock(), _context([_claim(_MEMBER, _FIVE_MEMBERS, FilledBy.ELECTED_BY_VOTERS)] * 2), MagicMock())

    assert next_state == OrganizationsCollectorStep.WRITE


@pytest.mark.asyncio
async def test_verify_asks_nothing_again_once_the_cap_stopped_extract():
    claims = [_claim(_MEMBER, _NOT_IN_THE_LAW, FilledBy.ELECTED_BY_VOTERS)] * 2

    verified, next_state = await verify(MagicMock(), MagicMock(), _context(claims, stopped_at_cost_cap=True), MagicMock())

    assert next_state == OrganizationsCollectorStep.WRITE
    assert verified.data.outcomes is not None and verified.data.outcomes.re_ask == [_MEMBER]
