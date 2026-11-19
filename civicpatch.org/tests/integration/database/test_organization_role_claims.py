"""A person's claim about the roles an organization holds outlives pipeline 2's answer: a rerun on
changed law keeps it, and a place copying that answer by its input hash does not get it.

Isolation: state 'zz', two sentinel places, cleaned before and after.
"""

import json

import pytest
import pytest_asyncio

from core.organization_derivation import ROLES_FIELD
from database import claims
from database import organizations as organizations_db
from database.changesets import create_roster_edit_changeset
from database.database import get_pool
from database.extras_organizations import get_extras_organizations_by_input_hash, save_extras_organizations
from database.roles import get_taxonomy_for
from database.users import SYSTEM_USER_ID
from schemas.claims import Claim, ClaimKind, EntityType, Source
from shared.schemas import GoverningLawOrganizations
from shared.utils.id_utils import make_id

_TOWN = "ocd-jurisdiction/country:us/state:zz/place:zz_role_claims/government"
_TWIN = "ocd-jurisdiction/country:us/state:zz/place:zz_role_claims_twin/government"
_HASH = "zz-role-claims-hash"
_BOARD = "Selectboard"


def _answer(collected_at: str, *roles: str) -> GoverningLawOrganizations:
    source = {"url": "https://example.gov/charter", "note": "the quote", "extras": {"source_page_id": "p1", "matched_in": "sentence"}}
    return GoverningLawOrganizations.model_validate(
        {
            "posts": [{"role": role, "label": role.title(), "organization_id": _BOARD, "sources": [source]} for role in roles],
            "extras": {"governing_law_collected_at": collected_at, "input_hash": _HASH},
        }
    )


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for ocdid in (_TOWN, _TWIN):
            # Changesets before organizations; the claims go with their changeset.
            await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (ocdid,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _seeded():
    await _wipe()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for ocdid in (_TOWN, _TWIN):
            await cur.execute(
                "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, status, data) VALUES (%s, 'zz', 'local', 'active', %s::jsonb)",
                (ocdid, json.dumps({"name": ocdid})),
            )
            await cur.execute("INSERT INTO organizations (jurisdiction_ocdid, name) VALUES (%s, %s)", (ocdid, _BOARD))
        await conn.commit()
    yield
    await _wipe()


async def _save(ocdid: str, answer: GoverningLawOrganizations) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await save_extras_organizations(cur, ocdid, answer)
        await conn.commit()


async def _reject_role(ocdid: str, role: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT id::text FROM organizations WHERE jurisdiction_ocdid = %s AND name = %s", (ocdid, _BOARD))
        (organization_id,) = await cur.fetchone()
        changeset_id = make_id()
        await create_roster_edit_changeset(cur, changeset_id, ocdid, SYSTEM_USER_ID)
        await claims.upsert(
            cur,
            Claim(
                entity_type=EntityType.ORGANIZATION,
                entity_id=organization_id,
                field_path=ROLES_FIELD,
                kind=ClaimKind.REJECT,
                value={"role": role, "label": role.title()},
                sources=[Source(url="https://example.gov/town-meeting-minutes")],
                changeset_id=changeset_id,
            ),
            SYSTEM_USER_ID,
        )
        await conn.commit()


async def _board_roles(ocdid: str) -> set[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        labels = await organizations_db.role_labels_by_name(cur, ocdid, await get_taxonomy_for(ocdid))
    return set(labels.get(_BOARD, {}))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_rejected_role_stays_rejected_when_pipeline_2_reruns_on_changed_law():
    await _save(_TOWN, _answer("2026-11-01T00:00:00Z", "member", "lister"))
    await _reject_role(_TOWN, "lister")

    await _save(_TOWN, _answer("2026-11-19T00:00:00Z", "member", "lister", "moderator"))

    assert await _board_roles(_TOWN) == {"member", "moderator"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_place_copying_the_answer_by_its_input_hash_does_not_get_another_place_s_claim():
    await _save(_TOWN, _answer("2026-11-01T00:00:00Z", "member", "lister"))
    await _reject_role(_TOWN, "lister")

    copied = await get_extras_organizations_by_input_hash(_HASH)
    assert copied is not None
    await _save(_TWIN, copied)

    assert await _board_roles(_TWIN) == {"member", "lister"}
    assert await _board_roles(_TOWN) == {"member"}
