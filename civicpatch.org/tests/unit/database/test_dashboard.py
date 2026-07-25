import datetime

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.dashboard import get_dashboard


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
async def test_get_dashboard_shapes_rows_per_state():
    # One cutoff for every row: it's the start of the rolling freshness window, which the
    # query computes once rather than reading per state.
    cutoff = datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc)
    rows = [
        # (state, known, scrapeable, covered_fresh, covered_stale, officials,
        #  status_fresh, status_stale, status_gap, status_untracked, cutoff)
        ("co", 271, 250, 90, 30, 850, 90, 30, 130, 21, cutoff),
        ("tx", 1221, 900, 300, 100, 3200, 300, 100, 700, 121, cutoff),
    ]
    cur = _make_cursor(rows)
    with patch("database.dashboard.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_dashboard()

    assert result == {
        "states": {
            "co": {
                "state": "co",
                "civicpatch": {
                    "officials": 850,
                    "cutoff": cutoff.isoformat(),
                    "localities": {
                        "known": 271,
                        "scrapeable": 250,
                        "covered": 120,  # covered_fresh + covered_stale
                        "covered_fresh": 90,
                        "covered_stale": 30,
                    },
                    "status_counts": {
                        "fresh": 90,
                        "stale": 30,
                        "gap": 130,
                        "untracked": 21,
                    },
                },
            },
            "tx": {
                "state": "tx",
                "civicpatch": {
                    "officials": 3200,
                    "cutoff": cutoff.isoformat(),
                    "localities": {
                        "known": 1221,
                        "scrapeable": 900,
                        "covered": 400,
                        "covered_fresh": 300,
                        "covered_stale": 100,
                    },
                    "status_counts": {
                        "fresh": 300,
                        "stale": 100,
                        "gap": 700,
                        "untracked": 121,
                    },
                },
            },
        }
    }


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_dashboard_empty_when_no_rows():
    cur = _make_cursor([])
    with patch("database.dashboard.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_dashboard()

    assert result == {"states": {}}
