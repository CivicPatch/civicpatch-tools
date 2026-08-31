"""Integration tests for `assertions` — what a human said about a row.

Against the real DB because the guarantees under test are constraints and derivation, not
Python: the CHECKs, `UNIQUE NULLS NOT DISTINCT`, and `DISTINCT ON` picking the latest.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from psycopg.errors import CheckViolation, ForeignKeyViolation, NotNullViolation

from core.post_derivation import DerivedMember
from database import assertions, divisions, memberships, organizations, posts
from database.database import get_pool
from schemas.assertions import Assertion, AssertionKind, EntityType, Source

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_assert/government"
_BASE = "ocd-division/country:us/state:zz/place:zz_assert"
_USER = "zz-assert-user@example.com"
_SEEN_AT = datetime(2026, 3, 11, tzinfo=timezone.utc)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM assertions WHERE asserted_by IN "
            "(SELECT id FROM users WHERE email = %s)",
            (_USER,),
        )
        await cur.execute("DELETE FROM users WHERE email = %s", (_USER,))
        # Before `jurisdictions`: `requests.jurisdiction_ocdid` is a FK, so one left behind
        # takes the whole module down at setup.
        # Memberships before posts (FK), and people after them.
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        for table in ("posts", "divisions", "organizations", "changesets", "people"):
            await cur.execute(
                f"DELETE FROM {table} WHERE jurisdiction_ocdid = %s", (_OCDID,)
            )
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed() -> tuple[str, str]:
    """A user to assert, and a post to assert about."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, role) "
            "VALUES (%s, 'email', %s, 'admins') RETURNING id::text",
            (_USER, _USER),
        )
        user_id = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        organization_id = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, organization_id, "mayor", _BASE)
        # A held seat somewhere else in the jurisdiction, so this is not its first scrape:
        # `unverified_by_jurisdiction` says nothing where nobody holds anything, and without
        # this the vouching test below would pass for the wrong reason.
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name) "
            "VALUES (gen_random_uuid(), %s, 'Seated Elsewhere') RETURNING id::text",
            (_OCDID,),
        )
        seated = (await cur.fetchone())[0]
        # `assessor` because the tests below mint `clerk` and `treasurer` themselves and
        # expect those unverified — a collision here hands them back this held one.
        other = await posts.find_or_create(
            cur, _OCDID, organization_id, "assessor", _BASE
        )
        await memberships.upsert(cur, DerivedMember(person_id=seated), other, organization_id, _SEEN_AT)
        await conn.commit()
    return user_id, post_id


def _verified(rows: list[dict], post_id: str) -> bool:
    """By id, not by position. `_seed` now holds a second seat so the jurisdiction is past its
    first scrape, and `list_for_jurisdiction` orders by role — so `rows[0]` silently became a
    different post than the one under test."""
    return next(row for row in rows if row["id"] == post_id)["_is_verified"]


def _vouch(post_id: str, **overrides) -> Assertion:
    """"There really are five trustees" — a claim about `_headcount`, with why attached.

    Vouching has no shape of its own since 137: it is an ordinary field assertion, which is why
    it survived the loss of `confirm`.
    """
    return Assertion(
        entity_type=EntityType.POST,
        entity_id=post_id,
        field_path="_headcount",
        value=5,
        kind=AssertionKind.ACCEPT,
        sources=[Source(note="phoned the clerk, there really are five trustees")],
        **overrides,
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_vouching_for_a_post_verifies_it_without_a_publish():
    """The case that could not be done any other way. A transient's request was superseded, so
    publishing it is refused by the guard — the rows most needing human judgement were
    permanently locked out of receiving it."""
    user_id, post_id = await _seed()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        rows = await posts.list_for_jurisdiction(cur, _OCDID)
        assert _verified(rows, post_id) is False
        # The review queue reads the same fact through a different query. Asserted together
        # because the screen saying "unverified" while the queue stops asking is the failure
        # neither test catches alone.
        unverified = await posts.unverified_by_jurisdiction(cur, [_OCDID])
        assert [post["id"] for post in unverified[_OCDID]] == [post_id]

    await assertions.create(_vouch(post_id), user_id)

    async with pool.connection() as conn, conn.cursor() as cur:
        rows = await posts.list_for_jurisdiction(cur, _OCDID)
        assert await posts.unverified_by_jurisdiction(cur, [_OCDID]) == {_OCDID: []}
    assert _verified(rows, post_id) is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_hand_made_post_is_verified_by_having_been_made():
    """Nobody has to vouch separately. Creating a post is somebody saying it exists, so it reads
    verified without a publish and without a second action — which is what `created_by` was
    briefly a column for, before `change_logs` turned out to already record it.

    The derivation's path leaves one unverified, because nothing there is claiming anything.
    """
    user_id, _ = await _seed()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await organizations.find_or_create(cur, _OCDID)
        derived = await posts.find_or_create(
            cur, _OCDID, organization_id, "clerk", _BASE
        )
        await conn.commit()

    by_hand = await posts.create(_OCDID, "treasurer", _BASE, 1, user_id)

    async with pool.connection() as conn, conn.cursor() as cur:
        verified = {
            row["id"]: row["_is_verified"]
            for row in await posts.list_for_jurisdiction(cur, _OCDID)
        }
    assert verified[by_hand] is True
    assert verified[derived] is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_looking_again_refreshes_rather_than_accumulating():
    """A no-op edit is somebody saying "I looked and it stands". Since `insert` upserts, saying
    it again moves `asserted_at` instead of adding a row — which is what keeps this table
    bounded by distinct values rather than by how often anyone looks."""
    user_id, _ = await _seed()
    post_id = await posts.create(_OCDID, "treasurer", _BASE, 1, user_id)

    for _ in range(3):
        assert await posts.update(post_id, 1, True, user_id) is True

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        rows = (await assertions.list_for_entities(cur, EntityType.POST, [post_id])).get(post_id, [])

    assert sorted(row["field_path"] for row in rows) == ["_headcount", "_is_tracked"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_evidence_survives():
    """`sources` is the reason vouching is not just `posts.updated_by`. A column records who,
    never why, and "phoned the clerk" exists nowhere else — it came from outside a publish."""
    user_id, post_id = await _seed()
    await assertions.create(_vouch(post_id), user_id)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        rows = (await assertions.list_for_entities(cur, EntityType.POST, [post_id])).get(post_id, [])

    assert len(rows) == 1
    assert rows[0]["sources"][0]["note"].startswith("phoned the clerk")
    assert rows[0]["asserted_by_name"] == _USER


@pytest.mark.asyncio
@pytest.mark.integration
async def test_stating_a_scalar_field_twice_replaces_rather_than_accumulates():
    """One answer per scalar field, held by a unique index rather than by every reader
    remembering to take the latest. `change_logs` keeps what the earlier answer was."""
    user_id, _ = await _seed()
    person_id = str(uuid.uuid4())

    for value in ("first@town.gov", "second@town.gov"):
        await assertions.create(
            Assertion(
                entity_type=EntityType.PERSON,
                entity_id=person_id,
                field_path="name",
                kind=AssertionKind.ACCEPT,
                value=value,
            ),
            user_id,
        )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        stated = (await assertions.stated_values(cur, EntityType.PERSON, [person_id])).get(person_id, {})
        rows = (await assertions.list_for_entities(cur, EntityType.PERSON, [person_id])).get(person_id, [])

    assert stated["name"][AssertionKind.ACCEPT] == ["second@town.gov"]
    assert len(rows) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_stating_a_claim_drops_only_its_opposite_about_the_same_value():
    """A save recomputes a few fields; a person carries claims from every scrape before it,
    because publishing accepts every value the reviewer saw. So a write must take out the
    claim it contradicts and nothing else — otherwise correcting a phone in April silently
    un-rejects the wrong email somebody caught in March.
    """
    user_id, _ = await _seed()
    person_id = str(uuid.uuid4())

    def claim(field, kind, value):
        return Assertion(
            entity_type=EntityType.PERSON,
            entity_id=person_id,
            field_path=field,
            kind=kind,
            value=value,
        )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for c in [
                claim("phones", AssertionKind.REJECT, "(555) 0001"),
                claim("phones", AssertionKind.ACCEPT, "(555) 0002"),
                claim("emails", AssertionKind.REJECT, "typo@town.gov"),
        ]:
            await assertions.upsert(cur, c, user_id)
        # A later save puts the rejected number back and says nothing about the email.
        await assertions.upsert(cur, claim("phones", AssertionKind.ACCEPT, "(555) 0001"), user_id)
        stated = (
            await assertions.stated_values(cur, EntityType.PERSON, [person_id])
        ).get(person_id, {})
        await conn.commit()

    assert stated["phones"][AssertionKind.REJECT] == []
    assert sorted(stated["phones"][AssertionKind.ACCEPT]) == ["(555) 0001", "(555) 0002"]
    # Untouched by a save about phones.
    assert stated["emails"][AssertionKind.REJECT] == ["typo@town.gov"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_list_field_accumulates_one_row_per_element():
    """A list field is a set, so each element stands on its own — a reviewer rejecting one phone
    number must not have to restate the others."""
    user_id, _ = await _seed()
    person_id = str(uuid.uuid4())

    for value in ("(555) 0001", "(555) 0002"):
        await assertions.create(
            Assertion(
                entity_type=EntityType.PERSON,
                entity_id=person_id,
                field_path="phones",
                kind=AssertionKind.ACCEPT,
                value=value,
            ),
            user_id,
        )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        stated = (await assertions.stated_values(cur, EntityType.PERSON, [person_id])).get(person_id, {})

    assert sorted(stated["phones"][AssertionKind.ACCEPT]) == ["(555) 0001", "(555) 0002"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_withdrawing_stops_the_claim():
    """Undo is a delete since 137. Append-only needed a third kind whose only job was to cancel
    a row it could not remove — and that could never express *un-rejecting*, since accepting a
    value you had rejected forces it to be the value rather than merely unblocking it."""
    user_id, _ = await _seed()
    person_id = str(uuid.uuid4())

    await assertions.create(
        Assertion(
            entity_type=EntityType.PERSON,
            entity_id=person_id,
            field_path="name",
            kind=AssertionKind.ACCEPT,
            value="Wrong Name",
        ),
        user_id,
    )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        assert await assertions.withdraw(cur, EntityType.PERSON, person_id, "name") == 1
        await conn.commit()

    async with pool.connection() as conn, conn.cursor() as cur:
        assert (await assertions.stated_values(cur, EntityType.PERSON, [person_id])).get(person_id, {}) == {}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_assertion_nobody_made_is_refused():
    """`asserted_by` is NOT NULL, unlike `requests.resolved_by_user_id` where NULL means a
    machine gave up. Nothing machine-generated belongs in here."""
    _, post_id = await _seed()

    with pytest.raises(ForeignKeyViolation):
        await assertions.create(_vouch(post_id), str(uuid.uuid4()))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unknown_entity_type_is_refused():
    """A CHECK rather than free text: `entity_type` is joined against by every reader, and a
    typo would silently make an assertion invisible instead of failing."""
    user_id, post_id = await _seed()

    pool = await get_pool()
    with pytest.raises(CheckViolation):
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO assertions "
                "(entity_type, entity_id, field_path, value, kind, asserted_by) "
                "VALUES ('organisation', %s, 'name', '\"x\"', 'accept', %s)",
                (post_id, user_id),
            )
            await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_assertion_about_nothing_is_refused():
    """Both columns are NOT NULL since 137, and that is what dissolved "what does `value = NULL`
    mean" — clearing a phone is a *reject of that number*, never a null accept."""
    user_id, post_id = await _seed()

    pool = await get_pool()
    with pytest.raises(NotNullViolation):
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO assertions (entity_type, entity_id, kind, asserted_by) "
                "VALUES ('post', %s, 'accept', %s)",
                (post_id, user_id),
            )
            await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_vouch_does_not_stop_the_voucher_deleting_the_post():
    """A person's *history* blocks a delete; their *opinion* does not.

    Somebody who vouched for a post and has since decided it is wrong is the very person
    deleting it. The vouch goes with the post — `assertions` has no foreign key, so leaving it
    would orphan a row pointing at nothing.
    """
    user_id, post_id = await _seed()
    await assertions.create(_vouch(post_id), user_id)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        assert await posts.delete_if_unheld(cur, post_id) is True
        rows = (await assertions.list_for_entities(cur, EntityType.POST, [post_id])).get(post_id, [])
        assert rows == []
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_post_someone_holds_cannot_be_deleted():
    """Memberships are somebody's history, and the FK would refuse anyway — this makes it a 409
    a reviewer can act on rather than a 500. Acting on it means re-pointing them first."""
    user_id, post_id = await _seed()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await organizations.find_or_create(cur, _OCDID)
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name) VALUES (%s, %s, %s)",
            (person_id := str(uuid.uuid4()), _OCDID, "Holder"),
        )
        await memberships.upsert(
            cur, DerivedMember(person_id=person_id), post_id, organization_id, datetime.now(timezone.utc)
        )
        assert await posts.delete_if_unheld(cur, post_id) is False
        await conn.rollback()
