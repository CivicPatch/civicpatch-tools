from enum import StrEnum

from pydantic import BaseModel


class Bucket(StrEnum):
    BLOCKED = "blocked"
    TO_REVIEW = "to_review"
    SCRAPING = "scraping"
    DONE = "done"
    QUEUED = "queued"


class MapStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    GAP = "gap"
    UNTRACKED = "untracked"


class StateCoverage(BaseModel):
    total: int
    scrapeable: int
    done: int
    done_over_scrapeable_fraction: float
    done_over_total_fraction: float
    buckets: dict[Bucket, int]


def summarize_state_coverage(
    total: set[str],
    scrapeable: set[str],
    done: set[str],
    blocked: set[str],
    to_review: set[str],
    scraping: set[str],
) -> StateCoverage:
    buckets = {bucket: 0 for bucket in Bucket}
    done_count = 0
    for ocdid in scrapeable:
        if ocdid in done:
            done_count += 1  # done-wins: count it even if it also lands in a flight bucket
        # first match wins → priority blocked > to_review > scraping > done > queued
        if ocdid in blocked:
            buckets[Bucket.BLOCKED] += 1
        elif ocdid in to_review:
            buckets[Bucket.TO_REVIEW] += 1
        elif ocdid in scraping:
            buckets[Bucket.SCRAPING] += 1
        elif ocdid in done:
            buckets[Bucket.DONE] += 1
        else:
            buckets[Bucket.QUEUED] += 1

    scrapeable_count = len(scrapeable)
    total_count = len(total)
    return StateCoverage(
        total=total_count,
        scrapeable=scrapeable_count,
        done=done_count,
        done_over_scrapeable_fraction=(
            done_count / scrapeable_count if scrapeable_count else 0.0
        ),
        done_over_total_fraction=done_count / total_count if total_count else 0.0,
        buckets=buckets,
    )


def classify_map_status(
    *, has_people: bool, is_fresh: bool, has_url: bool
) -> MapStatus:
    # Two axes: has-data, and (when it has data) freshness vs the state's cutoff.
    # is_fresh is only meaningful with people; has_url only when there are none.
    if has_people:
        return MapStatus.FRESH if is_fresh else MapStatus.STALE
    return MapStatus.GAP if has_url else MapStatus.UNTRACKED
