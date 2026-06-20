from datetime import datetime

from schemas.common import ReviewMode


def review_mode_for(scraped_at: datetime | None) -> ReviewMode:
    return ReviewMode.BASELINE if scraped_at is None else ReviewMode.RECONCILE
