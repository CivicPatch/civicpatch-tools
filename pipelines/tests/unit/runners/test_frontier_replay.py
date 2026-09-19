"""The replay harness itself: does re-ranking a saved queue answer a question we can trust.

Not a gate on crawl quality. These assert the tool works — deterministic, reads a real saved
context, and reports a rank rather than a yes/no — so a candidate sort key can be measured
against the shipped one on the same 50-odd saved queues. `mise run frontier-report` prints the
measurement; this keeps the thing that prints it honest.
"""

import pytest

from runners.people_collector.schemas import Link, LinkFrontier, LinkStatus
from runners.people_collector.utils.organization_terms import as_tokens, organization_phrases
from shared.schemas import KnownOrganization, Post
from shared.utils.url_utils import canonical_url
from tests.unit.runners.frontier_replay import (
    all_links,
    load_frontier,
    ordered,
    pending,
    rank_of,
    productive_urls,
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
    council page outranks one linked once, whichever organization needs people."""
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


def test_an_organization_beats_a_page_linked_from_everywhere():
    """The shipped change: `num_references` is self-reinforcing, so an organization linked once used to
    lose to a councilmember bio linked from every council page."""
    frontier = _frontier(
        ("https://zz.gov/council/members/ana", 9, LinkStatus.PENDING.value),
        ("https://zz.gov/school-board", 1, LinkStatus.PENDING.value),
    )

    order = [link.url for link in ordered(frontier, designations=["School Board"])]

    assert order[0] == "https://zz.gov/school-board"


def test_references_still_break_a_tie_between_two_organizations():
    """Demoted, not deleted: with nothing to tell two links apart, the better-linked one is
    still the better guess."""
    frontier = _frontier(
        ("https://zz.gov/school-board/members", 1, LinkStatus.PENDING.value),
        ("https://zz.gov/school-board", 4, LinkStatus.PENDING.value),
    )

    order = [link.url for link in ordered(frontier, designations=["School Board"])]

    assert order[0] == "https://zz.gov/school-board"


def test_organization_terms_keep_what_distinguishes_an_organization():
    organizations = [
        KnownOrganization(id="a", name="School Board", posts=[]),
        KnownOrganization(id="b", name="Office of the Mayor", posts=[]),
    ]

    assert as_tokens(organization_phrases(organizations, [])) == ["school", "board", "mayor"]


def test_organization_terms_drop_words_every_municipal_site_uses():
    """"City" or "office" as a search term ranks /city-hall-hours and /clerks-office alongside
    the roster, which is the opposite of the point."""
    organizations = [KnownOrganization(id="a", name="City Council", posts=[])]

    assert as_tokens(organization_phrases(organizations, [])) == ["council"]


def test_post_labels_are_terms_too():
    organizations = [
        KnownOrganization(
            id="a",
            name="Board of Trustees",
            posts=[
                Post(
                    id="p",
                    jurisdiction_ocdid="ocd-jurisdiction/country:us/state:zz/place:zz/government",
                    organization_id="a",
                    role_id="trustee",
                    division_ocdid="ocd-division/country:us/state:zz/place:zz",
                    label="Trustee, Ward 3",
                )
            ],
        )
    ]

    assert as_tokens(organization_phrases(organizations, [])) == ["board", "trustees", "trustee", "ward"]


def test_outcomes_come_from_the_records_source_urls():
    """The only outcome label the saved runs carry, and it was never written down for this: a
    record keeps the page it was read from, so a link either produced people or did not."""
    contexts = [path for path in saved_contexts() if productive_urls(path)]
    if not contexts:
        pytest.skip("no saved run produced records")

    for path in contexts[:5]:
        productive = productive_urls(path)
        links = {canonical_url(link.url) for link in all_links(load_frontier(path))}
        # Every productive url is a link the run held: otherwise the label cannot be scored
        # against an ordering of those links.
        assert productive <= links, path
