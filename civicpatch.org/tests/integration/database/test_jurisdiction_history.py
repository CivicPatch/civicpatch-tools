"""Integration tests for the roster changes a jurisdiction's history carries.

Real Postgres: the grouping and the type filter are both SQL, so neither can be checked by
unit-testing the mapper alone.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import json
import uuid

import pytest
import pytest_asyncio

from database import jurisdictions as db_jurisdictions
from database.database import get_pool
from database.changesets import live_roster_changeset
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
        # Assertion badges resolve their subject against `people`, so those tests seed one.
        await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid = %s", (_OCDID,))
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
            INSERT INTO changesets (kind, jurisdiction_ocdid)
            VALUES ('scrape', %s)
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


async def _dismiss(changeset_id: str, reason: DismissalReason) -> None:
    """Through `dismiss_request`, the real write path.

    It used to hand-roll the UPDATE and write the reason only to the `dismiss_review` log, which
    is what let it keep passing after migration 161 moved the reason onto the changeset — a
    fixture that copies a write path drifts the moment that path changes.
    """
    await dismiss_request(changeset_id, reason)


async def _dismiss_without_a_reason(changeset_id: str) -> None:
    """A shape `dismiss_request` cannot produce: dismissed before any reason was recorded.

    Raw on purpose. 19 dev rows are in it, and the reader has to keep answering for them, so
    something has to seed it. Nothing writes it any more — see 161.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE changesets SET dismissed_at = now() WHERE id::text = %s",
            (changeset_id,),
        )


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


async def _seed_resolved() -> str:
    """History holds only resolved changesets, so a test that wants to read one back has to
    resolve it first. Publishing is the cheap way; the dismissal tests seed pending and dismiss
    instead, because `changesets_publish_state_check` forbids a row being both."""
    changeset_id = await _seed_changeset()
    await _publish(changeset_id)
    return changeset_id


async def _entry_for(changeset_id: str):
    _, history = await db_jurisdictions.get_jurisdiction_history(_OCDID)
    return next(e for e in history if e.changeset_id == changeset_id)


async def _changes_for(changeset_id: str):
    _, history = await db_jurisdictions.get_jurisdiction_history(_OCDID)
    entry = next(e for e in history if e.changeset_id == changeset_id)
    return entry.changes


@pytest.mark.asyncio
@pytest.mark.integration
async def test_roster_changes_are_grouped_under_their_changeset():
    """Every roster type in one list, badged together. Person edits belong here because a hand
    edit mints its own changeset — they are that changeset's own work, not a pile accumulating
    on somebody else's row."""
    changeset_id = await _seed_resolved()
    await _log(
        changeset_id,
        ChangeLogType.ADD_PERSON,
        {"entity_type": "person", "entity_id": "p1", "subject": "Ann Lee", "fields": []},
    )
    await _log(
        changeset_id,
        ChangeLogType.EDIT_PERSON,
        {
            "entity_type": "person",
            "entity_id": "p1",
            "subject": "Ann Lee",
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
    """`publish_review` and `dismiss_review` say what happened to the review, not to the people.
    They share the changeset, so only the type filter keeps them out."""
    changeset_id = await _seed_resolved()
    await _log(changeset_id, ChangeLogType.PUBLISH_REVIEW, {})
    await _log(changeset_id, ChangeLogType.DISMISS_REVIEW, {"reason": "no_longer_valid"})

    assert await _changes_for(changeset_id) == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_seat_change_reads_as_a_post_field_change():
    """A move and a first assignment are one type; the `post_id` change's `before` tells them
    apart, and it is what the timeline renders."""
    changeset_id = await _seed_resolved()
    await _log(
        changeset_id,
        ChangeLogType.ASSIGN_MEMBERSHIP,
        {
            "entity_type": "membership",
            "entity_id": "m1",
            "subject": "Ann Lee",
            "detail": "council-member",
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
async def test_a_pending_changeset_is_not_in_the_history_at_all():
    """Was `test_a_pending_changeset_has_no_outcome_yet`, asserting `outcome == "pending"`.
    History is what happened, and a changeset nobody has decided has not happened yet — it
    belongs to `get_in_flight`, and the page shows it in its own section. So the claim moves
    from "it has no outcome" to "it is not here"."""
    changeset_id = await _seed_changeset()

    _, history = await db_jurisdictions.get_jurisdiction_history(_OCDID)

    assert [entry.changeset_id for entry in history] == []
    assert changeset_id is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_publishing_is_its_own_outcome_and_names_who_did_it():
    user_id = await _seed_user()
    changeset_id = await _seed_changeset()
    await _publish(changeset_id, user_id)

    entry = await _entry_for(changeset_id)

    assert entry.outcome == "published"
    assert entry.resolved_by == "Ada Reviewer"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_dismissal_reports_the_reason_it_recorded():
    """Off `changesets.dismissed_reason`, which every dismissal path writes.

    It used to be read from the `dismiss_review` log, which only `dismiss_request` wrote — so the
    sweeps' dismissals had no reason any reader could see, and 249 of 381 resolved changesets
    rendered "unknown" while the column said superseded or unchanged. Migration 161.
    """
    changeset_id = await _seed_changeset()
    await _dismiss(changeset_id, DismissalReason.SUPERSEDED)

    assert (await _entry_for(changeset_id)).outcome == "superseded"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_dismissal_with_no_recorded_reason_reads_as_unknown():
    """19 dev rows are in exactly this shape — dismissed before any reason was stored, and
    scattered across eight dates rather than one operation. Guessing one from `status` would
    put a reason in the reader's hands that nobody recorded.

    Closed to new rows: all four producers write a reason, so this set only shrinks.
    """
    changeset_id = await _seed_changeset()
    await _dismiss_without_a_reason(changeset_id)

    assert (await _entry_for(changeset_id)).outcome == "unknown"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_dismissal_nobody_asked_for_is_credited_to_the_system():
    """A supersede sweep is an actor. Before 160 this left `resolved_by_user_id` null, which
    read the same as a person whose display name is unset.

    This replaced `test_nobody_is_named_when_nobody_resolved_it`, which asserted the opposite —
    that such a dismissal reports no resolver. That shape is unreachable: `dismiss_request`
    COALESCEs to the system user, and 0 of 381 resolved changesets on dev have a null resolver.
    """
    changeset_id = await _seed_changeset()

    await dismiss_request(changeset_id, DismissalReason.SUPERSEDED, None)

    entry = await _entry_for(changeset_id)
    assert entry.resolved_by == "CivicPatch"
    assert entry.outcome == "superseded"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_first_dismissal_reason_stands():
    """A second close cannot rewrite why the first one happened.

    This inverts `test_the_latest_close_wins`, which asserted that a later `dismiss_review` log
    overrode the earlier reason. It could, while the log was the source. Now the reason sits
    beside `dismissed_at` and both are COALESCEd on write: a dismissal is one event, so it
    cannot have the time of the first and the reason of the second.
    """
    changeset_id = await _seed_changeset()
    await _dismiss(changeset_id, DismissalReason.SUPERSEDED)
    await _dismiss(changeset_id, DismissalReason.REJECTED)

    assert (await _entry_for(changeset_id)).outcome == "superseded"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_nothing_is_live_before_the_first_publish():
    await _seed_changeset()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        assert await live_roster_changeset(cur, _OCDID) is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_pending_scrape_is_never_the_live_roster():
    """The trap the name guards: an edit filed under an unaccepted scrape."""
    published = await _seed_changeset()
    await _publish(published)
    await _seed_changeset()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        assert await live_roster_changeset(cur, _OCDID) == published


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_newest_publish_is_the_live_roster():
    await _publish(await _seed_changeset())
    newest = await _seed_changeset()
    await _publish(newest)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        assert await live_roster_changeset(cur, _OCDID) == newest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_changeset_with_nothing_logged_carries_an_empty_list():
    """The join is a LEFT JOIN: a changeset that produced no roster change is still an entry."""
    changeset_id = await _seed_resolved()

    assert await _changes_for(changeset_id) == []


# ── Assertion subjects: the one badge whose name is not in its payload ──


async def _seed_person(name: str) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO people (jurisdiction_ocdid, name) VALUES (%s, %s) RETURNING id::text",
            (_OCDID, name),
        )
        return (await cur.fetchone())[0]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_details_edit_shows_what_it_changed():
    """A `jurisdiction_edit` changeset is in this list by design (decision D), so its log has to
    be too — otherwise the row reads "No roster changes" while the log holds the field diff.
    The subject is the place; there is no person or seat to name."""
    changeset_id = await _seed_resolved()
    await _log(
        changeset_id,
        ChangeLogType.EDIT_JURISDICTION,
        {
            "entity_type": "jurisdiction",
            "entity_id": _OCDID,
            "subject": "Crystal town",
            "fields": [{"field": "url", "before": "", "after": "https://example.test"}],
        },
    )

    changes = await _changes_for(changeset_id)

    assert [change.name for change in changes] == ["Crystal town"]
    assert [field.field for field in changes[0].fields] == ["url"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_scrape_entry_carries_its_run_s_clock_not_the_changeset_s():
    """A scrape's changeset is minted at ingest with `updated_at == created_at`, so a duration
    measured off it reads 0s for a run that took minutes. Seattle read `SUCCESS 0s` for a run
    that took 9m12s."""
    pool = await get_pool()
    changeset_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, data, status) "
            "VALUES (%s, 'zz', 'local', '{}'::jsonb, 'active') ON CONFLICT DO NOTHING",
            (_OCDID,),
        )
        await cur.execute(
            "INSERT INTO changesets (id, jurisdiction_ocdid, kind, created_at, updated_at, "
            "published_at) VALUES (%s, %s, 'scrape', now(), now(), now())",
            (changeset_id, _OCDID),
        )
        await cur.execute(
            "INSERT INTO pipeline_runs (id, jurisdiction_ocdid, arguments_json, status, "
            "changeset_id, created_at, finished_at) VALUES (%s, %s, '{}'::jsonb, 'SUCCESS', %s, "
            "now() - interval '9 minutes', now())",
            (run_id, _OCDID, changeset_id),
        )
        await conn.commit()

    _total, entries = await db_jurisdictions.get_jurisdiction_history(_OCDID)
    entry = next(e for e in entries if e.changeset_id == changeset_id)

    assert entry.pipeline_run_started_at is not None
    assert entry.pipeline_run_finished_at is not None
    # The changeset's own two timestamps are equal, which is what made this read 0s.
    assert entry.created_at == entry.updated_at


@pytest.mark.asyncio
@pytest.mark.integration
async def test_only_a_scrape_carries_pipeline_run_timestamps():
    """A sheet import or a hand edit has no pipeline run, so it has no duration to report — and
    the changeset's own timestamps are not one."""
    pool = await get_pool()
    changeset_id = str(uuid.uuid4())
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, data, status) "
            "VALUES (%s, 'zz', 'local', '{}'::jsonb, 'active') ON CONFLICT DO NOTHING",
            (_OCDID,),
        )
        await cur.execute(
            "INSERT INTO changesets (id, jurisdiction_ocdid, kind, created_at, updated_at, "
            "published_at) VALUES (%s, %s, 'people_edit', now(), now(), now())",
            (changeset_id, _OCDID),
        )
        await conn.commit()

    _total, entries = await db_jurisdictions.get_jurisdiction_history(_OCDID)
    entry = next(e for e in entries if e.changeset_id == changeset_id)

    assert entry.pipeline_run_started_at is None
    assert entry.pipeline_run_finished_at is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_entry_carries_the_issues_still_open_on_it():
    """The Seattle entry read `SUCCESS 0s, rejected` with no hint that the run had stopped at
    its cost cap — the one fact that explained the short roster."""
    pool = await get_pool()
    changeset_id = str(uuid.uuid4())
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, data, status) "
            "VALUES (%s, 'zz', 'local', '{}'::jsonb, 'active') ON CONFLICT DO NOTHING",
            (_OCDID,),
        )
        await cur.execute(
            "INSERT INTO changesets (id, jurisdiction_ocdid, kind, created_at, updated_at, "
            "published_at) VALUES (%s, %s, 'scrape', now(), now(), now())",
            (changeset_id, _OCDID),
        )
        await cur.execute(
            "INSERT INTO issues (issue_type, issue_key, changeset_ids, data, status) "
            "VALUES ('cost_cap_reached', %s, ARRAY[%s], '{}'::jsonb, 'pending')",
            (changeset_id, changeset_id),
        )
        await conn.commit()

    _total, entries = await db_jurisdictions.get_jurisdiction_history(_OCDID)
    entry = next(e for e in entries if e.changeset_id == changeset_id)

    assert entry.issue_types == ["cost_cap_reached"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_dismissal_says_why():
    """`dismissed_reason` was stored and never shown, so a dismissal read as motiveless."""
    pool = await get_pool()
    changeset_id = str(uuid.uuid4())
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, data, status) "
            "VALUES (%s, 'zz', 'local', '{}'::jsonb, 'active') ON CONFLICT DO NOTHING",
            (_OCDID,),
        )
        await cur.execute(
            "INSERT INTO changesets (id, jurisdiction_ocdid, kind, created_at, updated_at, "
            "dismissed_at, dismissed_reason) "
            "VALUES (%s, %s, 'scrape', now(), now(), now(), 'rejected')",
            (changeset_id, _OCDID),
        )
        await conn.commit()

    _total, entries = await db_jurisdictions.get_jurisdiction_history(_OCDID)
    entry = next(e for e in entries if e.changeset_id == changeset_id)

    assert entry.dismissed_reason == "rejected"
