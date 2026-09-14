from datetime import date

import pytest

from core.elections import filter_upcoming
from schemas.elections import Election

TODAY = date(2026, 9, 14)


def election(election_date, state="wa", title="General Election"):
    return Election(date=election_date, state=state, title=title)


@pytest.mark.unit
def test_filter_upcoming_drops_past_dates():
    past = election(date(2026, 9, 13))
    future = election(date(2026, 9, 15))

    assert filter_upcoming([past, future], TODAY) == [future]


@pytest.mark.unit
def test_filter_upcoming_keeps_today():
    today = election(TODAY)

    assert filter_upcoming([today], TODAY) == [today]


@pytest.mark.unit
def test_filter_upcoming_empty_list():
    assert filter_upcoming([], TODAY) == []
