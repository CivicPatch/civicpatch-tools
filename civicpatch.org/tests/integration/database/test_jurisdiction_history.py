"""Integration tests for the roster changes a jurisdiction's history carries.

Real Postgres: the grouping and the type filter are both SQL, so neither can be checked by
unit-testing the mapper alone.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import json

import pytest
import pytest_asyncio

from database import jurisdictions as db_jurisdictions
from database.database import get_pool
from database.publications import dismiss_request
from database.users import SYSTEM_USER_ID
from shared.utils.statuses import ChangeLogType, DismissalReason

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_history/government"
_USER_EMAIL = "zz-history-reviewer@example.test"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM change_logs WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        # This row only — `state = 'zz'` is shared with every other sentinel suite, and
        # deleting theirs takes their organizations' foreign keys down with it.
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute("DELETE FROM users WHERE email = %s", (_USER_EMAIL,))


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await _wipe()
    yield
    await _wipe()


async def _seed_changeset() -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # `changesets.jurisdiction_ocdid` is a foreign key, so the jurisdiction comes first.
        await cur.execute(
            """
            INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at)
            VALUES (%s, 'zz', '{}'::jsonb, now())
            ON CONFLICT (jurisdiction_ocdid) DO NOTHING
            """,
            (_OCDID,),
        )
        await cur.execute(
            """
            INSERT INTO changesets (kind, status, jurisdiction_ocdid, arguments_json)
            VALUES ('scrape', 'SUCCESS', %s, '{}'::jsonb)
            RETURNING id::text
            """,
            (_OCDID,),
        )
        return (await cur.fetchone())[0]


async def _log(changeset_id: str, type_: ChangeLogType, changes: dict) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO change_logs (type, jurisdiction_ocdid, changeset_id, changes, user_id)
            VALUES (%s, %s, %s, %s::jsonb, %s)
            """,
            (type_, _OCDID, changeset_id, json.dumps(changes), SYSTEM_USER_ID),
        )


async def _publish(changeset_id: str, user_id: str | None = None) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE changesets SET published_at = now(), resolved_by_user_id = %s "
            "WHERE id::text = %s",
            (user_id, changeset_id),
        )


async def _dismiss(changeset_id: str, reason: str | None) -> None:
    """Dismissed, and logged the way `dismiss_request` logs it. `reason=None` is the shape 32
    dev rows are already in — a dismissal whose log carries no reason."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE changesets SET dismissed_at = now() WHERE id::text = %s",
            (changeset_id,),
        )
    if reason is not None:
        await _log(changeset_id, ChangeLogType.CLOSE_REVIEW, {"reason": reason})


async def _seed_user() -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (email, provider, provider_user_id, display_name, role)
            VALUES (%s, 'test', %s, 'Ada Reviewer', 'maintainers')
            RETURNING id::text
            """,
            (_USER_EMAIL, _USER_EMAIL),
        )
        return (await cur.fetchone())[0]


async def _entry_for(changeset_id: str) -> dict:
    history = await db_jurisdictions.get_jurisdiction_history(_OCDID)
    return next(e for e in history if e["changeset_id"] == changeset_id)


async def _changes_for(changeset_id: str):
    history = await db_jurisdictions.get_jurisdiction_history(_OCDID)
    entry = next(e for e in history if e["changeset_id"] == changeset_id)
    return entry["changes"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_roster_changes_are_grouped_under_their_changeset():
    changeset_id = await _seed_changeset()
    await _log(
        changeset_id,
        ChangeLogType.ADD_PERSON,
        {"person_id": "p1", "person_name": "Ann Lee", "fields": []},
    )
    await _log(
        changeset_id,
        ChangeLogType.EDIT_PERSON,
        {
            "person_id": "p1",
            "person_name": "Ann Lee",
            "fields": [{"field": "name", "before": "A. Lee", "after": "Ann Lee"}],
        },
    )

    changes = await _changes_for(changeset_id)

    assert [c.type for c in changes] == ["add_person", "edit_person"]
    assert [c.name for c in changes] == ["Ann Lee", "Ann Lee"]
    assert [f.field for f in changes[1].fields] == ["name"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_review_lifecycle_is_not_a_roster_change():
    """`merge_review` and `close_review` say what happened to the review, not to the people.
    They share the changeset, so only the type filter keeps them out."""
    changeset_id = await _seed_changeset()
    await _log(changeset_id, ChangeLogType.MERGE_REVIEW, {})
    await _log(changeset_id, ChangeLogType.CLOSE_REVIEW, {"reason": "no_longer_valid"})

    assert await _changes_for(changeset_id) == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_seat_change_reads_as_a_post_field_change():
    """A move and a first assignment are one type; the `post_id` change's `before` tells them
    apart, and it is what the timeline renders."""
    changeset_id = await _seed_changeset()
    await _log(
        changeset_id,
        ChangeLogType.ASSIGN_MEMBERSHIP,
        {
            "membership_id": "m1",
            "person_id": "p1",
            "person_name": "Ann Lee",
            "post_id": "post-b",
            "role_id": "council-member",
            "fields": [{"field": "post_id", "before": "post-a", "after": "post-b"}],
        },
    )

    [change] = await _changes_for(changeset_id)

    assert change.name == "Ann Lee"
    assert [(f.field, f.before, f.after) for f in change.fields] == [
        ("post_id", "post-a", "post-b")
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_pending_changeset_has_no_outcome_yet():
    changeset_id = await _seed_changeset()

    assert (await _entry_for(changeset_id))["outcome"] == "pending"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_publishing_is_its_own_outcome_and_names_who_did_it():
    user_id = await _seed_user()
    changeset_id = await _seed_changeset()
    await _publish(changeset_id, user_id)

    entry = await _entry_for(changeset_id)

    assert entry["outcome"] == "published"
    assert entry["resolved_by"] == "Ada Reviewer"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_dismissal_reports_the_reason_its_log_recorded():
    """From the `close_review` log, never `changesets.dismissed_reason` — that column is
    legacy and null on every human dismissal."""
    changeset_id = await _seed_changeset()
    await _dismiss(changeset_id, "superseded")

    assert (await _entry_for(changeset_id))["outcome"] == "superseded"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_dismissal_with_no_recorded_reason_reads_as_unknown():
    """32 dev rows are in exactly this shape. Guessing one from `status` would put a reason in
    the reader's hands that nobody actually recorded."""
    changeset_id = await _seed_changeset()
    await _dismiss(changeset_id, None)

    assert (await _entry_for(changeset_id))["outcome"] == "unknown"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_nobody_is_named_when_nobody_resolved_it():
    changeset_id = await _seed_changeset()

    assert (await _entry_for(changeset_id))["resolved_by"] is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_dismissal_nobody_asked_for_is_credited_to_the_system():
    """A supersede sweep is an actor. Before 160 this left `resolved_by_user_id` null, which
    read the same as a person whose display name is unset."""
    changeset_id = await _seed_changeset()

    await dismiss_request(changeset_id, DismissalReason.SUPERSEDED, None)

    entry = await _entry_for(changeset_id)
    assert entry["resolved_by"] == "CivicPatch"
    assert entry["outcome"] == "superseded"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_latest_close_wins():
    """A card can be closed more than once — superseded, then rejected on a second pass."""
    changeset_id = await _seed_changeset()
    await _dismiss(changeset_id, "superseded")
    await _log(changeset_id, ChangeLogType.CLOSE_REVIEW, {"reason": "rejected"})

    assert (await _entry_for(changeset_id))["outcome"] == "rejected"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_changeset_with_nothing_logged_carries_an_empty_list():
    """The join is a LEFT JOIN: a changeset that produced no roster change is still an entry."""
    changeset_id = await _seed_changeset()

    assert await _changes_for(changeset_id) == []
