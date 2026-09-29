"""Opening a jurisdiction pull request against real rows: the jurisdiction, its config files and
its changesets. Only GitHub is mocked."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio

from database.database import get_pool
from database.changesets import has_rejected_jurisdiction_pull_request
from database.users import SYSTEM_USER_ID
from lib.github.api import PullRequestState
from services.government_form import government_form_choices
from services.jurisdiction_pull_request import (
    GovernmentFormNotAtLevel,
    JurisdictionEdit,
    PullRequestAlreadyOpen,
    UnknownJurisdiction,
    open_jurisdiction_pull_request,
    has_open_pull_request,
    fetch_pull_request_outcomes,
)
from shared.schemas import GovernmentForm
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import COUNTRY_ROLES_PATH, ConfigFile, ConfigRole, GovernmentFormConfig
from shared.utils.statuses import PullRequestLabel

_CITY = "ocd-jurisdiction/country:us/state:wa/place:zyprcity/government"
_LOCAL_FORMS = "data_source/local/config.yml"
_CONFIGS = {
    COUNTRY_ROLES_PATH: ConfigFile(roles=[ConfigRole(id="council-member", label="Council Member")]),
    _LOCAL_FORMS: ConfigFile(
        government_forms={
            GovernmentForm.MAYOR_COUNCIL: GovernmentFormConfig(
                organizations=[DerivedOrganization(name="Council", role_labels=["Council Member"])]
            ),
            GovernmentForm.COUNCIL_MANAGER: GovernmentFormConfig(
                organizations=[DerivedOrganization(name="Council", role_labels=["Council Member"])]
            ),
        }
    ),
}


async def _execute(sql, params=()):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _rows():
    await _execute(
        """
        INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at)
        VALUES (%s, 'wa', %s::jsonb, now()) ON CONFLICT (jurisdiction_ocdid) DO NOTHING
        """,
        (_CITY, json.dumps({"name": "Zyprcity city"})),
    )
    for path, config in _CONFIGS.items():
        await _execute(
            """
            INSERT INTO jurisdiction_configs (path, content, commit_sha) VALUES (%s, %s, 'test')
            ON CONFLICT (path) DO UPDATE SET content = EXCLUDED.content
            """,
            (path, config.model_dump_json()),
        )
    yield
    await _execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_CITY,))
    await _execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_CITY,))
    await _execute("DELETE FROM jurisdiction_configs WHERE path = ANY(%s)", (list(_CONFIGS),))


def _github_opens(number: int):
    return patch(
        "services.jurisdiction_pull_request._open_pr",
        new_callable=AsyncMock,
        return_value=(number, f"https://example.test/pull/{number}"),
    )


async def _open(form: GovernmentForm = GovernmentForm.MAYOR_COUNCIL, ocdid: str = _CITY):
    edit = JurisdictionEdit(patch={}, government_form=form, sources=["https://example.test"])
    return await open_jurisdiction_pull_request(ocdid, edit, PullRequestLabel.SYSTEM, SYSTEM_USER_ID)


async def _open_changesets() -> list[tuple[str, str]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT change_url, created_by_user_id::text FROM changesets
            WHERE jurisdiction_ocdid = %s AND published_at IS NULL AND dismissed_at IS NULL
            """,
            (_CITY,),
        )
        return list(await cur.fetchall())


async def _dismissed_reasons() -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT dismissed_reason FROM changesets WHERE jurisdiction_ocdid = %s AND dismissed_at IS NOT NULL",
            (_CITY,),
        )
        return [row[0] for row in await cur.fetchall()]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_pull_request_is_tracked_as_an_open_changeset_by_its_author():
    with _github_opens(7) as mock_github:
        opened = await _open()

    assert opened.pull_request_number == 7
    assert await _open_changesets() == [("https://example.test/pull/7", SYSTEM_USER_ID)]
    author = mock_github.call_args.args[3]
    assert author.name == "CivicPatch"


def _first_one_is(state: PullRequestState):
    return patch(
        "services.jurisdiction_pull_request._pull_request_state",
        new_callable=AsyncMock,
        return_value=state,
    )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("state", [PullRequestState.OPEN, PullRequestState.MERGED])
async def test_a_second_pull_request_waits_while_the_first_is_open_or_merged(state):
    """Merged but not synced in yet still waits: the sync publishes it."""
    with _github_opens(7):
        await _open()

    with _first_one_is(state), _github_opens(8) as mock_github, pytest.raises(PullRequestAlreadyOpen, match="pull/7"):
        await _open(GovernmentForm.COUNCIL_MANAGER)
    mock_github.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_closed_pull_request_is_rejected_and_a_new_one_opens():
    with _github_opens(7):
        await _open()

    with _first_one_is(PullRequestState.CLOSED), _github_opens(8):
        opened = await _open(GovernmentForm.COUNCIL_MANAGER)

    assert opened.pull_request_number == 8
    assert await _open_changesets() == [("https://example.test/pull/8", SYSTEM_USER_ID)]
    assert await _dismissed_reasons() == ["rejected"]
    assert await has_rejected_jurisdiction_pull_request(_CITY)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_form_of_another_level_is_refused():
    with _github_opens(7) as mock_github, pytest.raises(GovernmentFormNotAtLevel):
        await _open(GovernmentForm.COUNTY_EXECUTIVE)
    mock_github.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_unknown_jurisdiction_is_refused():
    missing = "ocd-jurisdiction/country:us/state:wa/place:zyprmissing/government"

    with _github_opens(7), pytest.raises(UnknownJurisdiction):
        await _open(ocdid=missing)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_run_sees_an_open_pull_request_as_waiting():
    with _github_opens(7):
        await _open()

    with _first_one_is(PullRequestState.OPEN):
        assert await has_open_pull_request(_CITY)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_run_settles_a_closed_one_as_rejected():
    with _github_opens(7):
        await _open()

    with _first_one_is(PullRequestState.CLOSED):
        assert not await has_open_pull_request(_CITY)
    assert await _dismissed_reasons() == ["rejected"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_run_counts_an_unreadable_one_as_waiting():
    with _github_opens(7):
        await _open()
    unreadable = httpx.HTTPStatusError("boom", request=httpx.Request("GET", "https://x"), response=httpx.Response(500))

    with patch(
        "services.jurisdiction_pull_request._pull_request_state",
        new_callable=AsyncMock,
        side_effect=unreadable,
    ):
        assert await has_open_pull_request(_CITY)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_settling_after_a_sync_publishes_a_merged_pull_request():
    with _github_opens(7):
        await _open()

    with _first_one_is(PullRequestState.MERGED):
        await fetch_pull_request_outcomes()

    assert await _open_changesets() == []
    assert await _dismissed_reasons() == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_settling_after_a_sync_rejects_a_closed_pull_request():
    with _github_opens(7):
        await _open()

    with _first_one_is(PullRequestState.CLOSED):
        await fetch_pull_request_outcomes()

    assert await _dismissed_reasons() == ["rejected"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_settling_leaves_an_open_pull_request_waiting():
    with _github_opens(7):
        await _open()

    with _first_one_is(PullRequestState.OPEN):
        await fetch_pull_request_outcomes()

    assert await _open_changesets() == [("https://example.test/pull/7", SYSTEM_USER_ID)]


# ── government_form_choices: whether a run asks the model ─────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_undecided_jurisdiction_is_offered_every_allowed_form():
    assert await government_form_choices(_CITY) == [GovernmentForm.MAYOR_COUNCIL, GovernmentForm.COUNCIL_MANAGER]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_choices_while_a_pull_request_waits():
    with _github_opens(7):
        await _open()

    with _first_one_is(PullRequestState.OPEN):
        assert await government_form_choices(_CITY) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_choices_once_a_person_closed_one():
    with _github_opens(7):
        await _open()

    with _first_one_is(PullRequestState.CLOSED):
        assert await government_form_choices(_CITY) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_choices_once_the_form_is_set():
    await _execute(
        "UPDATE jurisdictions SET data = data || %s::jsonb WHERE jurisdiction_ocdid = %s",
        (json.dumps({"extras": {"government_form": "mayor_council"}}), _CITY),
    )

    assert await government_form_choices(_CITY) == []
