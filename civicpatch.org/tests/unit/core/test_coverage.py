"""Unit tests for summarize_state_coverage (core/coverage.py).

summarize_state_coverage(total, scrapeable, covered_fresh, covered_stale, blocked, to_review,
scraping) -> StateCoverage
  - inputs: seven set[str] of jurisdiction ocdids for ONE state
  - total = all known; scrapeable ⊆ total = has url
  - covered_fresh = has officials AND scraped since cutoff; covered_stale = has officials but aging
    (disjoint; both subsets of scrapeable)
  - StateCoverage stores covered_fresh/covered_stale counts; done / reach_fraction / total_fraction
    are computed (done = covered_fresh + covered_stale)
  - buckets = each SCRAPEABLE ocdid in EXACTLY ONE pipeline bucket by priority
    blocked > to_review > scraping > done(fresh) > queued; stale falls into queued
    (it's a re-scrape candidate); sums to scrapeable

Rules pinned: (1) pipeline priority is exclusive and sums to scrapeable; (2) done-wins —
covered_fresh/covered_stale are tallied regardless of flight bucket, so done can exceed buckets[DONE].
"""

import pytest

from core.coverage import (
    Bucket,
    MapStatus,
    StateCoverage,
    classify_map_status,
    summarize_state_coverage,
)


def _summary(**kwargs) -> StateCoverage:
    base = {
        "total": set(),
        "scrapeable": set(),
        "covered_fresh": set(),
        "covered_stale": set(),
        "blocked": set(),
        "to_review": set(),
        "scraping": set(),
    }
    base.update(kwargs)
    return summarize_state_coverage(**base)


@pytest.mark.unit
def test_each_category_lands_in_its_own_bucket():
    # pin: one ocdid per category (+ jq in none) → each bucket gets exactly 1, queued = leftover
    result = _summary(
        total={"jb", "jr", "js", "jd", "jq", "ab", "ac", "ad"},
        scrapeable={"jb", "jr", "js", "jd", "jq"},
        blocked={"jb"},
        to_review={"jr"},
        scraping={"js"},
        covered_fresh={"jd"},
    )

    assert result.buckets[Bucket.BLOCKED] == 1
    assert result.buckets[Bucket.TO_REVIEW] == 1
    assert result.buckets[Bucket.SCRAPING] == 1
    assert result.buckets[Bucket.DONE] == 1
    assert result.buckets[Bucket.QUEUED] == 1


@pytest.mark.unit
def test_buckets_sum_to_scrapeable():
    # pin: the exclusivity invariant — sum(buckets.values()) == scrapeable
    result = _summary(
        scrapeable={"j1", "j2", "j3", "j4", "j5", "j6"},
        blocked={"j1"},
        to_review={"j2"},
        scraping={"j3"},
        covered_fresh={"j4", "j5"},
    )
    assert result.buckets == {
        Bucket.BLOCKED: 1,
        Bucket.TO_REVIEW: 1,
        Bucket.SCRAPING: 1,
        Bucket.DONE: 2,
        Bucket.QUEUED: 1,  # j6
    }
    assert sum(result.buckets.values()) == result.scrapeable == 6


@pytest.mark.unit
def test_blocked_beats_open_pr():
    # pin: an ocdid in BOTH blocked and to_review → bucket is blocked (review-pool overlap)
    result = _summary(scrapeable={"j1"}, blocked={"j1"}, to_review={"j1"})
    assert result.buckets[Bucket.BLOCKED] == 1
    assert result.buckets[Bucket.TO_REVIEW] == 0
    # ...but needs_review_count is orthogonal to bucket exclusivity: the open PR
    # still counts, even though the bucket-priority breakdown attributes it elsewhere.
    assert result.needs_review_count == 1


@pytest.mark.unit
def test_needs_review_count_is_the_raw_to_review_set_size():
    # pin: needs_review_count == len(to_review), independent of scrapeable/blocked
    result = _summary(scrapeable={"j1", "j2"}, to_review={"j1", "j2", "j3"})
    assert result.needs_review_count == 3


@pytest.mark.unit
def test_full_priority_order_blocked_wins_over_all():
    # pin: an ocdid in all four category sets → bucket is blocked, others 0
    result = _summary(
        scrapeable={"j1"},
        blocked={"j1"},
        to_review={"j1"},
        scraping={"j1"},
        covered_fresh={"j1"},
    )
    assert result.buckets == {
        Bucket.BLOCKED: 1,
        Bucket.TO_REVIEW: 0,
        Bucket.SCRAPING: 0,
        Bucket.DONE: 0,
        Bucket.QUEUED: 0,
    }
    assert result.covered == 1  # done-wins: still tallied


@pytest.mark.unit
def test_scraping_beats_done():
    # pin: mid-chain priority — in scraping AND covered_fresh → bucket is scraping
    result = _summary(scrapeable={"j1"}, scraping={"j1"}, covered_fresh={"j1"})
    assert result.buckets[Bucket.SCRAPING] == 1
    assert result.buckets[Bucket.DONE] == 0
    assert result.covered_fresh == 1  # done-wins


@pytest.mark.unit
def test_covered_fresh_wins_counts_despite_open_pr():
    # pin: fresh AND to_review → bucket=to_review, but covered_fresh/reach still count it
    result = _summary(scrapeable={"j1"}, covered_fresh={"j1"}, to_review={"j1"})
    assert result.buckets[Bucket.TO_REVIEW] == 1
    assert result.buckets[Bucket.DONE] == 0  # exclusive bucket excludes it
    assert result.covered_fresh == 1  # ...but the freshness tally includes it
    assert result.covered == 1
    assert result.reach_fraction == pytest.approx(1.0)


@pytest.mark.unit
def test_covered_fresh_wins_counts_despite_blocked():
    # pin: a new issue on a fresh ocdid doesn't drop it from the freshness tally
    result = _summary(scrapeable={"j1"}, covered_fresh={"j1"}, blocked={"j1"})
    assert result.buckets[Bucket.BLOCKED] == 1
    assert result.buckets[Bucket.DONE] == 0
    assert result.covered_fresh == 1
    assert result.reach_fraction == pytest.approx(1.0)


@pytest.mark.unit
def test_stale_counts_and_falls_into_queued():
    # pin: stale = has data but aging → counted as covered_stale, but bucketed QUEUED (re-scrape candidate)
    result = _summary(scrapeable={"j1"}, covered_stale={"j1"})
    assert result.covered_stale == 1
    assert result.covered_fresh == 0
    assert result.covered == 1  # it IS done (we have data)
    assert result.buckets[Bucket.QUEUED] == 1
    assert result.buckets[Bucket.DONE] == 0  # only fresh fills the DONE bucket


@pytest.mark.unit
def test_stale_wins_counts_despite_open_pr():
    # pin: stale with a re-scrape PR open → still tallied stale, bucketed to_review
    result = _summary(scrapeable={"j1"}, covered_stale={"j1"}, to_review={"j1"})
    assert result.covered_stale == 1
    assert result.buckets[Bucket.TO_REVIEW] == 1
    assert result.buckets[Bucket.QUEUED] == 0


@pytest.mark.unit
def test_fresh_stale_gap_split():
    # pin: fresh + stale + gap partition the scrapeable set
    result = _summary(
        scrapeable={"j1", "j2", "j3"},
        covered_fresh={"j1"},
        covered_stale={"j2"},  # j3 = gap
    )
    assert result.covered_fresh == 1
    assert result.covered_stale == 1
    assert result.covered == 2
    assert result.buckets[Bucket.DONE] == 1  # j1
    assert result.buckets[Bucket.QUEUED] == 2  # j2 (stale) + j3 (gap)
    assert result.reach_fraction == pytest.approx(2 / 3)


@pytest.mark.unit
def test_category_ocdids_outside_scrapeable_are_ignored():
    # pin: category sets carry non-scrapeable ocdids → ignored, don't inflate buckets/counts
    result = _summary(
        scrapeable={"j1"},
        scraping={"jx"},
        blocked={"jy"},
        covered_fresh={"jz"},
    )
    assert result.buckets == {
        Bucket.BLOCKED: 0,
        Bucket.TO_REVIEW: 0,
        Bucket.SCRAPING: 0,
        Bucket.DONE: 0,
        Bucket.QUEUED: 1,  # only j1, in no (scrapeable) category
    }
    assert result.covered == 0
    assert sum(result.buckets.values()) == result.scrapeable == 1


@pytest.mark.unit
def test_reach_fraction_is_done_over_scrapeable():
    # pin: reach ratio — 3 done of 4 scrapeable → 0.75
    result = _summary(
        scrapeable={"j1", "j2", "j3", "j4"},
        covered_fresh={"j1", "j2", "j3"},
    )
    assert result.covered == 3
    assert result.scrapeable == 4
    assert result.reach_fraction == pytest.approx(0.75)


@pytest.mark.unit
def test_total_fraction_uses_all_known_not_just_scrapeable():
    # pin: total denominator includes url-less jurisdictions → reach and total fractions differ
    result = _summary(
        total={"j1", "j2", "j3", "j4", "n1", "n2", "n3", "n4"},  # 8 known
        scrapeable={"j1", "j2", "j3", "j4"},  # 4 have urls
        covered_fresh={"j1", "j2"},  # 2 fresh
    )
    assert result.covered == 2
    assert result.reach_fraction == pytest.approx(0.5)  # 2/4
    assert result.total_fraction == pytest.approx(0.25)  # 2/8


@pytest.mark.unit
def test_empty_scrapeable_is_zero_not_division_error():
    # pin: scrapeable empty (other sets non-empty) → fractions 0.0, all buckets 0, no ZeroDivisionError
    result = _summary(scrapeable=set(), blocked={"j1"}, covered_fresh={"j2"})
    assert result.scrapeable == 0
    assert result.covered == 0
    assert result.reach_fraction == 0.0
    assert result.buckets == {
        Bucket.BLOCKED: 0,
        Bucket.TO_REVIEW: 0,
        Bucket.SCRAPING: 0,
        Bucket.DONE: 0,
        Bucket.QUEUED: 0,
    }


# ── classify_map_status ──────────────────────────────────────────────────────
# Two axes per jurisdiction → one of FRESH/STALE/GAP/UNTRACKED:
#   has people?  →  yes: fresh-since-cutoff splits FRESH vs STALE
#                   no:  has url splits GAP (scrapeable) vs UNTRACKED


@pytest.mark.unit
def test_map_has_people_and_fresh_is_fresh():
    assert (
        classify_map_status(has_people=True, is_fresh=True, has_url=True)
        == MapStatus.FRESH
    )


@pytest.mark.unit
def test_map_has_people_and_not_fresh_is_stale():
    assert (
        classify_map_status(has_people=True, is_fresh=False, has_url=True)
        == MapStatus.STALE
    )


@pytest.mark.unit
def test_map_no_people_with_url_is_gap():
    assert (
        classify_map_status(has_people=False, is_fresh=False, has_url=True)
        == MapStatus.GAP
    )


@pytest.mark.unit
def test_map_no_people_without_url_is_untracked():
    assert (
        classify_map_status(has_people=False, is_fresh=False, has_url=False)
        == MapStatus.UNTRACKED
    )


@pytest.mark.unit
def test_map_url_is_irrelevant_when_it_has_people():
    assert (
        classify_map_status(has_people=True, is_fresh=True, has_url=False)
        == MapStatus.FRESH
    )
    assert (
        classify_map_status(has_people=True, is_fresh=False, has_url=False)
        == MapStatus.STALE
    )


@pytest.mark.unit
def test_map_freshness_is_irrelevant_when_no_people():
    assert (
        classify_map_status(has_people=False, is_fresh=True, has_url=True)
        == MapStatus.GAP
    )
    assert (
        classify_map_status(has_people=False, is_fresh=True, has_url=False)
        == MapStatus.UNTRACKED
    )
