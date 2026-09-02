from enum import StrEnum

from pydantic import BaseModel, computed_field


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
    covered_fresh: int
    covered_stale: int
    buckets: dict[Bucket, int]
    # Raw count of jurisdictions with an open PR — orthogonal to `buckets`, which
    # is priority-exclusive (blocked wins over to_review) for the bucket
    # breakdown's sum-to-scrapeable invariant. A jurisdiction can be both
    # blocked AND need review; this field answers "how many need review" without
    # that exclusivity, matching services.coverage.get_municipality_list's
    # `needs_review` (same open_ocdids_by_state signal, unfiltered).
    needs_review_count: int

    @computed_field
    @property
    def covered(self) -> int:
        return self.covered_fresh + self.covered_stale

    @computed_field
    @property
    def reach_fraction(self) -> float:
        return self.covered / self.scrapeable if self.scrapeable else 0.0

    @computed_field
    @property
    def total_fraction(self) -> float:
        return self.covered / self.total if self.total else 0.0


def summarize_state_coverage(
    total: set[str],
    scrapeable: set[str],
    covered_fresh: set[str],
    covered_stale: set[str],
    blocked: set[str],
    to_review: set[str],
    scraping: set[str],
) -> StateCoverage:
    buckets = {bucket: 0 for bucket in Bucket}
    covered_fresh_count = 0
    covered_stale_count = 0
    for ocdid in scrapeable:
        # covered counts are done-wins: tallied regardless of which pipeline bucket it lands in
        if ocdid in covered_fresh:
            covered_fresh_count += 1
        elif ocdid in covered_stale:
            covered_stale_count += 1
        # pipeline bucket, first match wins → blocked > to_review > scraping > done(fresh) > queued
        # stale falls through to queued: it has data but is a re-scrape candidate
        if ocdid in blocked:
            buckets[Bucket.BLOCKED] += 1
        elif ocdid in to_review:
            buckets[Bucket.TO_REVIEW] += 1
        elif ocdid in scraping:
            buckets[Bucket.SCRAPING] += 1
        elif ocdid in covered_fresh:
            buckets[Bucket.DONE] += 1
        else:
            buckets[Bucket.QUEUED] += 1

    return StateCoverage(
        total=len(total),
        scrapeable=len(scrapeable),
        covered_fresh=covered_fresh_count,
        covered_stale=covered_stale_count,
        buckets=buckets,
        needs_review_count=len(to_review),
    )


def classify_map_status(
    *, has_people: bool, is_fresh: bool, has_url: bool
) -> MapStatus:
    # Two axes: has-data, and (when it has data) freshness vs the state's cutoff.
    # is_fresh is only meaningful with people; has_url only when there are none.
    if has_people:
        return MapStatus.FRESH if is_fresh else MapStatus.STALE
    return MapStatus.GAP if has_url else MapStatus.UNTRACKED
