import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import database.people as db_people


def _make_cursor(fetchall_side_effect):
    cur = AsyncMock()
    cur.execute = AsyncMock()
    cur.fetchall = AsyncMock(side_effect=fetchall_side_effect)
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
async def test_the_published_side_groups_by_jurisdiction():
    """Two requests for one place share its roster, so the read returns it once and the caller
    looks it up. It used to be keyed by request, which meant carrying the same list twice."""
    dallas = "ocd-jurisdiction/country:us/state:tx/place:dallas/government"
    austin = "ocd-jurisdiction/country:us/state:tx/place:austin/government"
    cur = _make_cursor([[(dallas, {"id": "p1"}), (dallas, {"id": "p2"}), (austin, {"id": "p3"})]])

    with patch("database.people.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await db_people.get_people_by_jurisdictions([dallas, austin])

    assert result == {dallas: [{"id": "p1"}, {"id": "p2"}], austin: [{"id": "p3"}]}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_no_jurisdictions_asks_nothing():
    cur = _make_cursor([[]])
    with patch("database.people.get_pool", AsyncMock(return_value=_make_pool(cur))) as pool:
        assert await db_people.get_people_by_jurisdictions([]) == {}
    pool.assert_not_awaited()


@pytest.mark.unit
def test_both_sides_of_the_card_carry_the_same_keys():
    """The published side is projected in SQL and the proposed side is a derived dict, so
    nothing but this keeps them in step — and the card diffs them key by key."""
    derived = {
        "id": "p1",
        "name": "Jane Doe",
        "labels": ["Mayor"],
        "source_urls": ["https://x.gov"],
        "phones": ["(555) 0001"],
        "cdn_image": "https://cdn/x.png",
        "jurisdiction_ocdid": "ocd-jurisdiction/x",
    }

    assert set(db_people.projected(derived, "quick")) == {
        "id", "name", "labels", "source_urls"
    }
    # Fields the view does not ask for are dropped, including ones only the derived side has.
    assert "phones" not in db_people.projected(derived, "quick")
    assert "cdn_image" not in db_people.projected(derived, "detail")
    assert set(db_people.projected(derived, "detail")) <= db_people.VIEWS["detail"]


@pytest.mark.unit
def test_memberships_reach_the_card_so_a_seated_person_is_not_asked_for_a_post():
    """The one key the two sides do *not* share, deliberately. `isPostUnanswered` treats an open
    membership as the post question already answered; without it in the projection a published
    person restored into the roster read as unanswered and blocked the publish.

    The proposed side has no memberships to carry — nothing is seated until a publish — so it
    simply lacks the key rather than carrying an empty one."""
    assert "memberships" in db_people.VIEWS["quick"]
    assert "memberships" in db_people.VIEWS["detail"]

    derived = {"id": "p1", "name": "Jane Doe", "labels": ["Mayor"]}
    assert "memberships" not in db_people.projected(derived, "quick")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_people_refuses_a_read_with_no_scope():
    with pytest.raises(db_people.UnscopedRead):
        await db_people.get_people()
