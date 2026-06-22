"""Unit tests for summarize_state_coverage (core/coverage.py).

summarize_state_coverage(total, scrapeable, done, blocked, to_review, scraping) -> StateCoverage
  - inputs: six set[str] of jurisdiction ocdids for ONE state
  - total = all known jurisdictions; scrapeable ⊆ total = the ones with a url
  - done = numerator (scraped_at >= cutoff)
  - done_over_scrapeable_fraction = done / scrapeable  (reach: progress on scrapeable work)
  - done_over_total_fraction      = done / total       (coverage of everything known)
    (both 0.0–1.0; 0.0 when the denominator is empty)
  - buckets = each SCRAPEABLE ocdid in EXACTLY ONE bucket by priority
              blocked > to_review > scraping > done > queued; sums to scrapeable

Two rules pinned below: (1) bucket priority is exclusive and sums to scrapeable;
(2) done-wins — done/fractions count scraped_at>=cutoff regardless of flight buckets,
so result.done can exceed buckets[DONE].
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
        "done": set(),
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
        done={"jd"},
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
        done={"j4", "j5"},
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
    result = _summary(
        scrapeable={"j1"},
        blocked={"j1"},
        to_review={"j1"},
    )
    assert result.buckets[Bucket.BLOCKED] == 1
    assert result.buckets[Bucket.TO_REVIEW] == 0


@pytest.mark.unit
def test_full_priority_order_blocked_wins_over_all():
    # pin: an ocdid in all four category sets → bucket is blocked, others 0
    result = _summary(
        scrapeable={"j1"},
        blocked={"j1"},
        to_review={"j1"},
        scraping={"j1"},
        done={"j1"},
    )
    assert result.buckets == {
        Bucket.BLOCKED: 1,
        Bucket.TO_REVIEW: 0,
        Bucket.SCRAPING: 0,
        Bucket.DONE: 0,
        Bucket.QUEUED: 0,
    }
    assert result.done == 1  # done-wins: still counted in the numerator


@pytest.mark.unit
def test_scraping_beats_done():
    # pin: mid-chain priority — in scraping AND done → bucket is scraping
    result = _summary(
        scrapeable={"j1"},
        scraping={"j1"},
        done={"j1"},
    )
    assert result.buckets[Bucket.SCRAPING] == 1
    assert result.buckets[Bucket.DONE] == 0
    assert result.done == 1  # done-wins


@pytest.mark.unit
def test_done_wins_percent_counts_done_despite_open_pr():
    # pin: in done AND to_review → bucket=to_review, but done/fraction still count it
    result = _summary(
        scrapeable={"j1"},
        done={"j1"},
        to_review={"j1"},
    )
    assert result.buckets[Bucket.TO_REVIEW] == 1
    assert result.buckets[Bucket.DONE] == 0  # the exclusive bucket excludes it
    assert result.done == 1  # ...but the numerator includes it
    assert result.done_over_scrapeable_fraction == pytest.approx(1.0)


@pytest.mark.unit
def test_done_wins_counts_done_despite_blocked():
    # pin: a new issue on a done ocdid doesn't dip the bar — done counts, bucket=blocked
    result = _summary(
        scrapeable={"j1"},
        done={"j1"},
        blocked={"j1"},
    )
    assert result.buckets[Bucket.BLOCKED] == 1
    assert result.buckets[Bucket.DONE] == 0
    assert result.done == 1
    assert result.done_over_scrapeable_fraction == pytest.approx(1.0)


@pytest.mark.unit
def test_category_ocdids_outside_scrapeable_are_ignored():
    # pin: category sets carry non-scrapeable ocdids → ignored, don't inflate buckets/done
    result = _summary(
        scrapeable={"j1"},
        scraping={"jx"},
        blocked={"jy"},
        done={"jz"},
    )
    assert result.buckets == {
        Bucket.BLOCKED: 0,
        Bucket.TO_REVIEW: 0,
        Bucket.SCRAPING: 0,
        Bucket.DONE: 0,
        Bucket.QUEUED: 1,  # only j1, and it's in no (scrapeable) category
    }
    assert result.done == 0  # jz is not scrapeable, so it's not in the numerator
    assert sum(result.buckets.values()) == result.scrapeable == 1


@pytest.mark.unit
def test_queued_is_everything_uncategorized():
    # pin: scrapeable ocdids in no category set → queued
    result = _summary(scrapeable={"j1", "j2", "j3"})
    assert result.buckets[Bucket.QUEUED] == 3
    assert result.done == 0


@pytest.mark.unit
def test_fraction_is_done_over_scrapeable():
    # pin: reach ratio — 3 done of 4 scrapeable → 0.75
    result = _summary(
        scrapeable={"j1", "j2", "j3", "j4"},
        done={"j1", "j2", "j3"},
    )
    assert result.done == 3
    assert result.scrapeable == 4
    assert result.buckets[Bucket.DONE] == 3
    assert result.buckets[Bucket.QUEUED] == 1  # j4
    assert result.done_over_scrapeable_fraction == pytest.approx(0.75)


@pytest.mark.unit
def test_done_over_total_uses_all_known_not_just_scrapeable():
    # pin: total denominator includes url-less jurisdictions → reach and total fractions differ
    result = _summary(
        total={"j1", "j2", "j3", "j4", "n1", "n2", "n3", "n4"},  # 8 known
        scrapeable={"j1", "j2", "j3", "j4"},  # 4 have urls
        done={"j1", "j2"},  # 2 scraped
    )
    assert result.done == 2
    assert result.done_over_scrapeable_fraction == pytest.approx(0.5)  # 2/4
    assert result.done_over_total_fraction == pytest.approx(0.25)  # 2/8


@pytest.mark.unit
def test_empty_scrapeable_is_zero_not_division_error():
    # pin: scrapeable empty (other sets non-empty) → fraction 0.0, all buckets 0, no ZeroDivisionError
    result = _summary(scrapeable=set(), blocked={"j1"}, done={"j2"})
    assert result.scrapeable == 0
    assert result.done == 0
    assert result.done_over_scrapeable_fraction == 0.0
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
    # with people, FRESH/STALE is decided by freshness alone — url doesn't change it
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
    # no people → GAP/UNTRACKED by url alone; a stray is_fresh=True doesn't make it FRESH
    assert (
        classify_map_status(has_people=False, is_fresh=True, has_url=True)
        == MapStatus.GAP
    )
    assert (
        classify_map_status(has_people=False, is_fresh=True, has_url=False)
        == MapStatus.UNTRACKED
    )
