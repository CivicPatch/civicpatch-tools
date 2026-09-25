"""Rolling back a user's hand-made claims.

Real Postgres: what this exists to prove is that a rollback is *visible*, not just recorded —
the withdrawn assertion has to stop winning the fold and the live `people` row has to change,
not only `claims.withdrawn_at`.

Run with: mise run tcp-integration
Isolation: sentinel state 'zz', cleaned before/after.
"""

import datetime
import uuid

import pytest
import pytest_asyncio

from core.post_derivation import DerivedMembership, MembershipSource
from database import divisions, organizations, posts
from database.database import get_pool
from database.source_records import insert_source_records
from schemas.common import Identity, UserRole
from schemas.jurisdictions import PersonEdit
from shared.utils.statuses import ChangesetKind
from services import rollback
from services.roster_edits import edit_published_roster
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:rollbackville/government"
_BASE = "ocd-division/country:us/state:zz/place:rollbackville"
_OTHER_OCDID = "ocd-jurisdiction/country:us/state:zz/place:rollback_other/government"
_OTHER_BASE = "ocd-division/country:us/state:zz/place:rollback_other"
_EMAIL = "zz-rollbackville-maintainer@example.com"
_OTHER_EMAIL = "zz-rollbackville-other@example.com"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for ocdid in (_OCDID, _OTHER_OCDID):
            await cur.execute(
                "DELETE FROM memberships m USING posts p "
                "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
                (ocdid,),
            )
            await cur.execute("DELETE FROM posts WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute(
                "DELETE FROM claims WHERE entity_id IN "
                "(SELECT id FROM people WHERE jurisdiction_ocdid = %s)",
                (ocdid,),
            )
            await cur.execute("DELETE FROM source_records WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM divisions WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (ocdid,))
        # A withdraw row is filed by the user too (214), and it names a claim, not a person.
        await cur.execute(
            "DELETE FROM claims WHERE created_by IN "
            "(SELECT id FROM users WHERE email IN (%s, %s))",
            (_EMAIL, _OTHER_EMAIL),
        )
        await cur.execute("DELETE FROM users WHERE email IN (%s, %s)", (_EMAIL, _OTHER_EMAIL))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean():
    await _wipe()
    yield
    await _wipe()


async def _create_user(email: str) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, username, role) "
            "VALUES (%s, 'github', %s, %s, %s) RETURNING id::text",
            (email, email, email.replace("@", "-"), UserRole.MAINTAINERS.value),
        )
        row = await cur.fetchone()
        assert row is not None
        await conn.commit()
    return row[0]


async def _seed_person(
    name: str,
    source_url: str,
    post_slug: str,
    label: str,
    jurisdiction_ocdid: str = _OCDID,
    base: str = _BASE,
) -> str:
    """A published person, on their own seat — what a hand edit rolls back."""
    person_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, status) "
            "VALUES (%s, 'zz', 'local', 'active') ON CONFLICT DO NOTHING",
            (jurisdiction_ocdid,),
        )
        await cur.execute(
            "SELECT id::text FROM changesets WHERE jurisdiction_ocdid = %s AND kind = 'scrape'",
            (jurisdiction_ocdid,),
        )
        row = await cur.fetchone()
        if row is not None:
            scrape_id = row[0]
        else:
            await cur.execute(
                "INSERT INTO changesets (kind, jurisdiction_ocdid, updated_at, published_at, created_at) "
                "VALUES ('scrape', %s, %s, now(), now()) RETURNING id::text",
                (jurisdiction_ocdid, datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc)),
            )
            row = await cur.fetchone()
            assert row is not None
            scrape_id = row[0]
        await cur.execute(
            "INSERT INTO people "
            "  (id, jurisdiction_ocdid, name, phones, source_urls, updated_at, "
            "   other_names, emails, urls) "
            "VALUES (%s, %s, %s, ARRAY[]::text[], ARRAY[%s], now(), "
            "        ARRAY[]::text[], ARRAY[]::text[], ARRAY[]::text[])",
            (person_id, jurisdiction_ocdid, name, source_url),
        )
        org = await organizations.find_or_create(cur, jurisdiction_ocdid)
        await divisions.find_or_create(cur, base, jurisdiction_ocdid)
        post_id = await posts.find_or_create(cur, jurisdiction_ocdid, org, post_slug, base)
        await factories.bind_membership(
            cur,
            DerivedMembership(person_id=person_id, sources=[MembershipSource(note=label)]),
            post_id,
            org,
            datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc),
        )
        await conn.commit()

    # A real person always has a sighting behind them — a rollback republish falls back to it,
    # so a person seeded with none has nothing to test that fallback against.
    await insert_source_records(
        scrape_id,
        jurisdiction_ocdid,
        {person_id: [{"name": name, "label": label, "source_url": source_url, "organization_id": org}]},
    )
    return person_id


def _identity(email: str, user_id: str) -> Identity:
    return Identity(
        type="session",
        provider="github",
        provider_user_id=email,
        email=email,
        role=UserRole.MAINTAINERS,
        user_id=user_id,
    )


_COMMENT = "rolled back in a test"


async def _rollback_user(created_by: str, user_id: str) -> int:
    """What a UI offering "roll back everything shown" does: list the user's candidates
    (flat, no jurisdiction chosen), then hand every id to the one executor — the same shape a
    selective call would use too, just with the full list rather than a hand-picked subset.

    Rollbacks are listed but excluded from "everything": undoing an undo is picking that one
    changeset deliberately, and sweeping them in would make select-all alternate between doing
    and undoing (settled 2026-09-24 with step 13). The screen does the same.
    """
    candidates = await rollback.list_user_changesets(created_by)
    return await rollback.rollback_changesets(
        [c.changeset_id for c in candidates if c.kind != ChangesetKind.ROLLBACK],
        user_id,
        _COMMENT,
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rollback_reverts_the_edit_and_republishes():
    user_id = await _create_user(_EMAIL)
    user = _identity(_EMAIL, user_id)
    person_id = await _seed_person("Ada Chen", "https://rollbackville.gov/mayor", "mayor", "Mayor")

    changeset_id = await edit_published_roster(
        _OCDID,
        [PersonEdit(id=person_id, fields={"name": "Ada M. Chen"})],
        user.user_id,
    )

    withdrawn = await _rollback_user(user_id, user_id)
    assert withdrawn == 1

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT name FROM people WHERE id::text = %s", (person_id,))
        row = await cur.fetchone()
        assert row is not None and row[0] == "Ada Chen", "the live row did not revert"

        await cur.execute(
            "SELECT withdrawn_at IS NOT NULL, withdrawn_by_changeset_id IS NOT NULL "
            "FROM claims WHERE changeset_id::text = %s",
            (changeset_id,),
        )
        assert await cur.fetchall() == [(True, True)]

        await cur.execute(
            "SELECT kind, published_at IS NOT NULL FROM changesets "
            "WHERE parent_changeset_id IS NOT NULL "
            "ORDER BY created_at DESC LIMIT 1",
        )
        assert await cur.fetchone() == ("rollback", True)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rollback_refuses_a_changeset_already_rolled_back():
    user_id = await _create_user(_EMAIL)
    user = _identity(_EMAIL, user_id)
    person_id = await _seed_person("Ada Chen", "https://rollbackville.gov/mayor", "mayor", "Mayor")

    await edit_published_roster(
        _OCDID, [PersonEdit(id=person_id, fields={"name": "Ada M. Chen"})], user.user_id
    )
    await _rollback_user(user_id, user_id)

    with pytest.raises(rollback.NothingToRollBack):
        await _rollback_user(user_id, user_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rollback_user_in_jurisdiction_reverts_only_that_users_edits():
    user_id = await _create_user(_EMAIL)
    other_user_id = await _create_user(_OTHER_EMAIL)
    user = _identity(_EMAIL, user_id)
    other_user = _identity(_OTHER_EMAIL, other_user_id)

    mine_id = await _seed_person("Ada Chen", "https://rollbackville.gov/mayor", "mayor", "Mayor")
    theirs_id = await _seed_person("Bo Nguyen", "https://rollbackville.gov/clerk", "clerk", "Clerk")

    # An edit names only who it changes. It used to have to name the whole roster, because
    # leaving somebody out retired them; the edit route says removal explicitly instead
    # (`posts: []`), so silence about a person means silence.
    await edit_published_roster(
        _OCDID, [PersonEdit(id=mine_id, fields={"name": "Ada M. Chen"})], user.user_id
    )
    await edit_published_roster(
        _OCDID,
        [PersonEdit(id=theirs_id, fields={"name": "Bo A. Nguyen"})],
        other_user.user_id,
    )

    withdrawn = await _rollback_user(user_id, user_id)
    assert withdrawn == 1

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text, name FROM people WHERE id::text IN (%s, %s)",
            (mine_id, theirs_id),
        )
        names = {row[0]: row[1] for row in await cur.fetchall()}
    assert names[mine_id] == "Ada Chen", "the target user's edit did not revert"
    assert names[theirs_id] == "Bo A. Nguyen", "an untouched user's edit was reverted"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rollback_user_in_jurisdiction_raises_when_nothing_to_roll_back():
    user_id = await _create_user(_EMAIL)
    await _seed_person("Ada Chen", "https://rollbackville.gov/mayor", "mayor", "Mayor")

    with pytest.raises(rollback.NothingToRollBack):
        await _rollback_user(user_id, user_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rollback_spans_multiple_jurisdictions_in_one_call():
    """No jurisdiction picker anywhere: a user's edits in two different places both revert from
    a single `list_user_changesets` + `rollback_changesets` call, each getting its own rollback
    changeset since a changeset belongs to exactly one jurisdiction."""
    user_id = await _create_user(_EMAIL)
    user = _identity(_EMAIL, user_id)

    here_id = await _seed_person("Ada Chen", "https://rollbackville.gov/mayor", "mayor", "Mayor")
    there_id = await _seed_person(
        "Cy Okonkwo",
        "https://other.gov/mayor",
        "mayor",
        "Mayor",
        jurisdiction_ocdid=_OTHER_OCDID,
        base=_OTHER_BASE,
    )

    await edit_published_roster(
        _OCDID, [PersonEdit(id=here_id, fields={"name": "Ada M. Chen"})], user.user_id
    )
    await edit_published_roster(
        _OTHER_OCDID,
        [PersonEdit(id=there_id, fields={"name": "Cy A. Okonkwo"})],
        user.user_id,
    )

    candidates = await rollback.list_user_changesets(user_id)
    assert {c.jurisdiction_ocdid for c in candidates} == {_OCDID, _OTHER_OCDID}

    withdrawn = await rollback.rollback_changesets(
        [c.changeset_id for c in candidates], user_id, _COMMENT
    )
    assert withdrawn == 2

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text, name FROM people WHERE id::text IN (%s, %s)",
            (here_id, there_id),
        )
        names = {row[0]: row[1] for row in await cur.fetchall()}
    assert names[here_id] == "Ada Chen"
    assert names[there_id] == "Cy Okonkwo"

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT jurisdiction_ocdid FROM changesets WHERE kind = 'rollback' "
            "AND jurisdiction_ocdid IN (%s, %s) ORDER BY jurisdiction_ocdid",
            (_OCDID, _OTHER_OCDID),
        )
        rollback_jurisdictions = [row[0] for row in await cur.fetchall()]
    assert rollback_jurisdictions == sorted([_OCDID, _OTHER_OCDID])


