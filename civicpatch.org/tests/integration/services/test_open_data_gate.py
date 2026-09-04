"""The open-data write gate: `commit_rendered_files` skips files open-data already holds.

Real Postgres for `output_hashes` — that table *is* what is under test — and a fake for the
GitHub call, which is network. The roster read is stubbed because what varies here is the
rendered bytes, not how they were derived; `test_roster_sheet` covers the gate against real
seeded data on the other sink.

What the stub cannot catch: that `open_data_records` renders stably for unchanged input. If it
ever emitted a timestamp or an unordered set, every file would look changed and the gate would
be silently dead — the same failure mode as hashing parquet's encoded bytes.
"""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from database.database import get_pool
from lib.temporal.types import OpenDataCommitItem
from services import publish as publish_service

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:gate/government"
_PATH = "data/us/zz/gate.yml"
_COMMIT = "https://github.com/CivicPatch/test-open-data/commit/abc123"

_ROSTER = [{"name": "Jane Doe", "jurisdiction_ocdid": _OCDID, "memberships": []}]
_CHANGED = [{"name": "Renamed Person", "jurisdiction_ocdid": _OCDID, "memberships": []}]


def _items() -> list[OpenDataCommitItem]:
    # No changeset ids: `record_change_url` is a separate concern with its own row to stamp.
    return [
        OpenDataCommitItem(
            file_path=_PATH, changeset_ids=[], jurisdiction_ocdid=_OCDID
        )
    ]


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM output_hashes WHERE target = %s", (_PATH,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean():
    await _wipe()
    yield
    await _wipe()


def _commit(roster, returns=_COMMIT):
    """Patch the two boundaries: what we render from, and where it goes."""
    return (
        patch("services.publish.get_roster", AsyncMock(return_value=roster)),
        patch(
            "services.publish.git_data.commit_github_files",
            AsyncMock(return_value=returns),
        ),
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_same_roster_is_not_committed_twice():
    """One email edit to Seattle produced three commits before this gate, two of them empty,
    because the sweep re-selects the same change over a lookback wider than its cadence."""
    roster_patch, commit_patch = _commit(_ROSTER)
    with roster_patch, commit_patch as fake_commit:
        assert await publish_service.commit_rendered_files(_items(), "first") == _COMMIT
        assert await publish_service.commit_rendered_files(_items(), "second") is None
        assert fake_commit.await_count == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_changed_roster_is_committed_again():
    roster_patch, commit_patch = _commit(_ROSTER)
    with roster_patch, commit_patch:
        await publish_service.commit_rendered_files(_items(), "first")

    roster_patch, commit_patch = _commit(_CHANGED)
    with roster_patch, commit_patch as fake_commit:
        assert await publish_service.commit_rendered_files(_items(), "second") == _COMMIT
        assert fake_commit.await_count == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_rejected_commit_raises_and_records_nothing():
    """A rejection is not a skip. Recording the hash before the ref moved would mark the file
    written when it never reached the branch, and every retry would then skip it."""
    roster_patch, commit_patch = _commit(_ROSTER, returns=None)
    with roster_patch, commit_patch:
        with pytest.raises(publish_service.OpenDataWriteRejected):
            await publish_service.commit_rendered_files(_items(), "rejected")

    roster_patch, commit_patch = _commit(_ROSTER)
    with roster_patch, commit_patch as fake_commit:
        assert await publish_service.commit_rendered_files(_items(), "retry") == _COMMIT
        assert fake_commit.await_count == 1
