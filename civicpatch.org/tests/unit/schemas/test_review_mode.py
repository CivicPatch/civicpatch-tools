import datetime

import pytest

from schemas.common import ReviewMode

pytestmark = pytest.mark.unit


def test_baseline_when_never_collected():
    assert ReviewMode.for_scrape(False) == ReviewMode.BASELINE


def test_reconcile_when_previously_collected():
    """A bool, not a timestamp. This took `jurisdictions.scraped_at` and compared it to None —
    the only question it ever asked. Passing a datetime still passed after the signature
    changed, because a datetime is truthy, which is why the argument is named now."""
    assert ReviewMode.for_scrape(True) == ReviewMode.RECONCILE
