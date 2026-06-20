import datetime

import pytest

from core.review_mode import review_mode_for
from schemas.common import ReviewMode

pytestmark = pytest.mark.unit


def test_baseline_when_never_scraped():
    assert review_mode_for(None) == ReviewMode.BASELINE


def test_reconcile_when_previously_scraped():
    scraped_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    assert review_mode_for(scraped_at) == ReviewMode.RECONCILE
