"""Caller-supplied source URLs are scraped before the jurisdiction's homepage.

The frontier is seeded with `config.url` before research runs, and `next_pending()` is strict
FIFO on the queue. Appending source URLs therefore put them *behind* the homepage: a run given
`https://www.seattle.gov/council` still scraped `https://seattle.gov` first, spending a fetch
and an LLM pass on a page of navigation links.

Someone naming the page the roster is on is the strongest signal the pipeline gets, so it goes
first. The homepage stays queued behind it — still available for discovering further pages.
"""

import pytest

from runners.people_collector.schemas import LinkFrontier

BASE = "https://seattle.gov"
SOURCE = "https://www.seattle.gov/council"


@pytest.mark.unit
def test_source_urls_are_scraped_before_the_seeded_base_url():
    frontier = LinkFrontier.from_urls([BASE]).add_front([SOURCE])

    assert frontier.next_pending().url == SOURCE


@pytest.mark.unit
def test_the_base_url_is_still_queued_behind_them():
    """Kept, not replaced — it is what discovery crawls when the source pages run out."""
    frontier = LinkFrontier.from_urls([BASE]).add_front([SOURCE])

    assert [frontier.links[k].url for k in frontier.queue] == [SOURCE, BASE]


@pytest.mark.unit
def test_several_source_urls_keep_their_given_order():
    first, second = "https://x.gov/council", "https://x.gov/mayor"
    frontier = LinkFrontier.from_urls([BASE]).add_front([first, second])

    assert [frontier.links[k].url for k in frontier.queue] == [first, second, BASE]


@pytest.mark.unit
def test_a_source_url_that_is_the_base_url_is_not_duplicated():
    frontier = LinkFrontier.from_urls([BASE]).add_front([BASE])

    assert len(frontier.queue) == 1
    assert len(frontier.links) == 1


@pytest.mark.unit
def test_add_still_appends():
    """`add` is what discovered links use — they belong at the back, unchanged."""
    discovered = "https://seattle.gov/departments"
    frontier = LinkFrontier.from_urls([BASE]).add([discovered])

    assert [frontier.links[k].url for k in frontier.queue] == [BASE, discovered]
