"""The replay harness itself: does re-ranking a saved queue answer a question we can trust.

Not a gate on crawl quality. These assert the tool works — deterministic, reads a real saved
context, and reports a rank rather than a yes/no — so a candidate sort key can be measured
against the shipped one on the same 50-odd saved queues. `mise run frontier-report` prints the
measurement; this keeps the thing that prints it honest.
"""

import pytest

from runners.people_collector.schemas import Link, LinkFrontier, LinkStatus
from tests.unit.runners.frontier_replay import (
    load_frontier,
    ordered,
    pending,
    rank_of,
    research_signals,
    saved_contexts,
    url_contains,
)

pytestmark = pytest.mark.unit


def _frontier(*links: tuple[str, int, str]) -> LinkFrontier:
    """`(url, references, status)` each, queued in the order given."""
    return LinkFrontier(
        links={
            url: Link(url=url, status=status, num_references=references)
            for url, references, status in links
        },
        queue=[url for url, _, _ in links],
    )


def test_a_page_already_read_is_not_ranked_again():
    frontier = _frontier(
        ("https://zz.gov/mayor", 2, LinkStatus.DONE.value),
        ("https://zz.gov/council", 3, LinkStatus.PENDING.value),
    )

    assert [link.url for link in pending(frontier)] == ["https://zz.gov/council"]


def test_references_decide_the_order_today():
    """The shipped key, and the bias the org-aware plan measured: a page linked from every
    council page outranks one linked once, whichever body needs people."""
    frontier = _frontier(
        ("https://zz.gov/mayor", 1, LinkStatus.PENDING.value),
        ("https://zz.gov/council/members/ana", 3, LinkStatus.PENDING.value),
    )

    assert [link.url for link in ordered(frontier)] == [
        "https://zz.gov/council/members/ana",
        "https://zz.gov/mayor",
    ]


def test_a_rank_says_how_far_down_not_merely_whether_it_is_there():
    """"The mayor's page is in the queue" was true in the run that stalled. Its rank was not."""
    frontier = _frontier(
        ("https://zz.gov/council/members/ana", 3, LinkStatus.PENDING.value),
        ("https://zz.gov/council/members/ben", 3, LinkStatus.PENDING.value),
        ("https://zz.gov/mayor", 1, LinkStatus.PENDING.value),
    )

    assert rank_of(ordered(frontier), url_contains("mayor")) == 3
    assert rank_of(ordered(frontier), url_contains("school-board")) is None


def test_ordering_the_same_queue_twice_gives_the_same_answer():
    """Otherwise a rank that moved between runs would mean nothing."""
    frontier = _frontier(
        ("https://zz.gov/a", 2, LinkStatus.PENDING.value),
        ("https://zz.gov/b", 2, LinkStatus.PENDING.value),
        ("https://zz.gov/c", 2, LinkStatus.PENDING.value),
    )

    assert [link.url for link in ordered(frontier)] == [link.url for link in ordered(frontier)]


def test_a_real_saved_run_replays():
    """The point of the harness: 50-odd real queues on disk, replayable with no network."""
    contexts = saved_contexts()
    if not contexts:
        pytest.skip("no saved pipeline_run_context.json in data_source")

    replayed = 0
    for path in contexts:
        frontier = load_frontier(path)
        names, designations = research_signals(path)
        links = ordered(frontier, names, designations)
        assert len(links) == len(pending(frontier))
        replayed += 1
    assert replayed == len(contexts)
