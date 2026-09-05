import datetime

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.coverage import get_municipality_rows_for_state


def _make_cursor(rows):
    cur = AsyncMock()
    cur.execute = AsyncMock()
    cur.fetchall = AsyncMock(return_value=rows)
    cur.__aenter__ = AsyncMock(return_value=cur)
    cur.__aexit__ = AsyncMock(return_value=False)
    return cur


def _make_pool(cursor):
    conn = AsyncMock()
    conn.cursor = MagicMock(return_value=cursor)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    pool = AsyncMock()
    pool.connection = MagicMock(return_value=conn)
    return pool


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_municipality_rows_classifies_status_per_row():
    collected_at = datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc)
    rows = [
        # (jurisdiction_ocdid, name, officials_count, collected_at, has_url, is_fresh)
        ("zz-fresh", "Fresh City", 5, collected_at, True, True),
        ("zz-stale", "Stale City", 3, collected_at, True, False),
        ("zz-gap", "Gap City", 0, None, True, False),
        ("zz-untracked", "Untracked City", 0, None, False, False),
    ]
    cur = _make_cursor(rows)
    with patch("database.coverage.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_municipality_rows_for_state("zz")

    assert result == [
        {
            "jurisdiction_ocdid": "zz-fresh",
            "name": "Fresh City",
            "status": "fresh",
            "officials_count": 5,
            "last_collected_at": collected_at.isoformat(),
        },
        {
            "jurisdiction_ocdid": "zz-stale",
            "name": "Stale City",
            "status": "stale",
            "officials_count": 3,
            "last_collected_at": collected_at.isoformat(),
        },
        {
            "jurisdiction_ocdid": "zz-gap",
            "name": "Gap City",
            "status": "gap",
            "officials_count": 0,
            "last_collected_at": None,
        },
        {
            "jurisdiction_ocdid": "zz-untracked",
            "name": "Untracked City",
            "status": "untracked",
            "officials_count": 0,
            "last_collected_at": None,
        },
    ]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_municipality_rows_empty_when_no_rows():
    cur = _make_cursor([])
    with patch("database.coverage.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_municipality_rows_for_state("zz")

    assert result == []
