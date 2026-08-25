import datetime

import pytest

from schemas.common import ReviewMode

pytestmark = pytest.mark.unit


def test_baseline_when_never_scraped():
    assert ReviewMode.for_scrape(None) == ReviewMode.BASELINE


def test_reconcile_when_previously_scraped():
    scraped_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    assert ReviewMode.for_scrape(scraped_at) == ReviewMode.RECONCILE
