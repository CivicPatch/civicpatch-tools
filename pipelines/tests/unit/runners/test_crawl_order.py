"""The next page comes from the least-crawled site section.

Seattle, 2026-09-16: ranking put six councilmember pages ahead of `/mayor`, because every council
page crawled added a reference to each councilmember link. The run never reached the Office of
the Mayor.
"""

import pytest

from runners.people_collector.schemas import Link, LinkFrontier, LinkStatus
from runners.people_collector.utils.crawl_order import least_crawled_section_first, url_section

_BASE = "https://seattle.gov"


@pytest.mark.unit
def test_a_section_not_yet_crawled_goes_ahead_of_a_better_ranked_link_in_a_crawled_one():
    queue = [
        f"{_BASE}/council/members/dionne-foster",
        f"{_BASE}/council/members/eddie-lin",
        f"{_BASE}/mayor",
    ]
    crawled = [_BASE, f"{_BASE}/council", f"{_BASE}/council/members/rob-saka"]

    assert least_crawled_section_first(queue, crawled) == f"{_BASE}/mayor"


@pytest.mark.unit
def test_ranking_decides_between_equally_crawled_sections():
    queue = [f"{_BASE}/mayor", f"{_BASE}/cityattorney", f"{_BASE}/council"]

    assert least_crawled_section_first(queue, crawled=[_BASE]) == f"{_BASE}/mayor"


@pytest.mark.unit
def test_ranking_decides_within_a_section():
    queue = [f"{_BASE}/council/members/dionne-foster", f"{_BASE}/council/members/eddie-lin"]

    assert (
        least_crawled_section_first(queue, crawled=[_BASE, f"{_BASE}/mayor"])
        == f"{_BASE}/council/members/dionne-foster"
    )


@pytest.mark.unit
def test_an_empty_queue_has_nothing_next():
    assert least_crawled_section_first([], crawled=[_BASE]) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("url", "section"),
    [
        ("https://seattle.gov", ""),
        ("https://seattle.gov/", ""),
        ("https://seattle.gov/council", "council"),
        ("https://seattle.gov/Council/Members/rob-saka", "council"),
    ],
)
def test_url_section_is_the_first_path_segment(url, section):
    assert url_section(url) == section


@pytest.mark.unit
def test_the_frontier_counts_every_page_that_is_no_longer_pending_as_crawled():
    """A page mid-scrape has already spent its fetch, so it counts."""
    council, members, mayor = f"{_BASE}/council", f"{_BASE}/council/members", f"{_BASE}/mayor"
    frontier = LinkFrontier(
        links={
            council: Link(url=council, status=LinkStatus.SCRAPED.value),
            members: Link(url=members, status=LinkStatus.PENDING.value),
            mayor: Link(url=mayor, status=LinkStatus.PENDING.value),
        },
        queue=[members, mayor],
    )

    next_link = frontier.next_pending()
    assert next_link is not None and next_link.url == mayor
