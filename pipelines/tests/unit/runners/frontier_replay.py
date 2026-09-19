"""Replay a saved crawl queue through the frontier's ordering, offline.

The frontier is pure data and pure functions, and `data_source` keeps a real
`pipeline_run_context.json` per jurisdiction, so "where would this page rank" is answerable with
no network, no LLM and no database. It is the only part of the pipeline with no harness: prompts
have evals, the derivation has integration tests, crawl order has nothing, which is why the
ordering change in the org-aware plan is deferred rather than guessed at.

Used by `test_frontier_replay.py` and by `mise run frontier-report`.
"""

import json
import pathlib
from typing import Callable, Iterable

from runners.people_collector.schemas import Link, LinkFrontier, LinkStatus, OrganizationNeed
from shared.utils.url_utils import canonical_url
from runners.people_collector.steps.step_04_process_page_content.organization_progress import (
    required_to_be_done,
)
from runners.people_collector.utils.link_discovery import (
    _compute_link_signals,
    _pending_sort_key,
)
from runners.people_collector.utils.organization_terms import as_tokens
from shared.utils import url_utils

DATA_SOURCE = pathlib.Path("data_source")


def saved_contexts(root: pathlib.Path = DATA_SOURCE) -> list[pathlib.Path]:
    """Every saved run, newest layout only: `<state>/local/<place>/pipeline_run_context.json`."""
    return sorted(root.glob("*/local/*/pipeline_run_context.json"))


def load_frontier(context_path: pathlib.Path) -> LinkFrontier:
    data = json.loads(context_path.read_text(encoding="utf-8"))["data"]
    return LinkFrontier.model_validate(data["frontier"])


def research_signals(context_path: pathlib.Path) -> tuple[list[str], list[str]]:
    """The names and designations the sort key scores links against, as that run had them."""
    data = json.loads(context_path.read_text(encoding="utf-8"))["data"]
    research = data.get("research_municipality_step") or {}
    return list(research.get("identities") or {}), list(research.get("known_roles") or [])


def productive_urls(context_path: pathlib.Path) -> set[str]:
    """The pages this run actually got records from, canonicalised.

    The only outcome label the saved runs carry: every record keeps the `source_url` it was read
    from, so a link either produced people or it did not. Nothing was written down for this
    purpose, which is why it is reconstructed here rather than read from a field.
    """
    data = json.loads(context_path.read_text(encoding="utf-8"))["data"]
    records = (data.get("process_page_content_step") or {}).get("records") or {}
    return {
        canonical_url(record["source_url"])
        for group in records.values()
        for record in group
        if record.get("source_url")
    }


def all_links(frontier: LinkFrontier) -> list[Link]:
    """Every link the run ever held, fetched or not.

    `pending` answers "what would it do next"; this answers "in what order would it have worked
    through everything", which is the question an outcome can score.
    """
    return [link for key in frontier.links if (link := frontier.links.get(key))]


def pending(frontier: LinkFrontier) -> list[Link]:
    return [
        link
        for key in frontier.queue
        if (link := frontier.links.get(key)) and link.status == LinkStatus.PENDING.value
    ]


def ordered(
    frontier: LinkFrontier,
    names: Iterable[str] = (),
    designations: Iterable[str] = (),
    key: Callable | None = None,
) -> list[Link]:
    """The pending queue as `add_relevant_urls` would leave it after its next re-sort.

    Takes the sort key as an argument so a candidate ordering can be measured against the
    shipped one on the same saved queues.
    """
    sort_key = key or shipped_key([])
    return sorted(
        pending(frontier), key=lambda link: sort_key(link, list(names), list(designations))
    )


def shipped_key(needs: list[OrganizationNeed]) -> Callable:
    """`_pending_sort_key` with a run's organizations bound, in the shape candidates share."""
    return lambda link, names, designations: _pending_sort_key(link, needs, names, designations)


def rank_of(links: list[Link], matches: Callable[[Link], bool]) -> int | None:
    """1-based position of the first matching link, or None when nothing matches.

    A rank, not a boolean: "the mayor's page is in the queue" was always true in the run that
    stalled. What mattered was that it sat behind eight councilmember bios.
    """
    for position, link in enumerate(links, start=1):
        if matches(link):
            return position
    return None


def url_contains(fragment: str) -> Callable[[Link], bool]:
    return lambda link: fragment in link.url.lower()


def organization_first_key(link: Link, names: list[str], designations: list[str]) -> tuple:
    """Candidate: a link naming a role or organization we are looking for outranks reference count.

    The shipped key scores references second, which is self-reinforcing — every council page
    crawled adds a reference to every councilmember link — so an organization linked once is buried by a
    organization linked from its own section. This moves the designation match above it. Designation, not
    `role`: the caller folds `known_roles` into `designations` (`add_relevant_urls` is passed
    `designations + known_roles`), and the key never passes `roles` at all, so `signals.role` is
    always None and the term is dead.

    Not shipped. It exists to be measured against `_pending_sort_key` on the saved queues.
    """
    signals = _compute_link_signals(link.url, link.text or "", designations, names=names)
    return (
        -int(signals.keyword is not None),
        -int(signals.designation is not None),
        -link.num_references,
        -int(signals.name is not None),
        -int(signals.role is not None),
        len(url_utils.get_path(link.url).split("/")),
    )


# Segments that mean "this page is about officials doing things", not "this page lists them".
# A date is the strongest of them: /2026/... is an archive path on every CMS.
NOISE_SEGMENTS = ("news", "press", "blog", "announcement", "announcements", "archive",
                  "archives", "agenda", "agendas", "minutes", "calendar", "events", "event")


def _is_year(segment: str) -> bool:
    return len(segment) == 4 and segment.isdigit() and segment.startswith(("19", "20"))


def _segments(url: str) -> list[str]:
    return [segment for segment in url_utils.get_path(url).split("/") if segment]


def _noise(url: str) -> bool:
    segments = [segment.lower() for segment in _segments(url)]
    return any(_is_year(segment) or segment in NOISE_SEGMENTS for segment in segments)


def _match_count(url: str, text: str, terms: list[str]) -> int:
    """How many of the terms this link matches, rather than whether any did.

    `/government/city-council` matches "government" and "council"; `/2026/news/mayor` matches
    "mayor". The shipped key scores both as one boolean and cannot tell them apart.
    """
    haystack = f"{url} {text}".lower()
    return sum(1 for term in terms if term and term.lower() in haystack)


def path_shape_key(link: Link, names: list[str], designations: list[str]) -> tuple:
    """Candidate: demote archive-shaped urls, then count matching terms, then references.

    Deterministic on purpose. The alternative — learning a ranker — has no training set here,
    because nothing records whether fetching a link produced records, and a key that cannot be
    replayed against the saved queues cannot be argued with.
    """
    signals = _compute_link_signals(link.url, link.text or "", designations, names=names)
    return (
        int(_noise(link.url)),
        -int(signals.keyword is not None),
        -_match_count(link.url, link.text or "", designations),
        -link.num_references,
        -int(signals.name is not None),
        len(_segments(link.url)),
    )


def _need(
    organization_id: str, required: int, found: int, phrases: list[str], missing: list[str]
) -> OrganizationNeed:
    target = required_to_be_done(required)
    return OrganizationNeed(
        organization_id=organization_id,
        shortfall=max(0, target - found) / target,
        terms=as_tokens(phrases),
        missing_terms=as_tokens(missing),
    )


_SEATTLE_COUNCIL_POSTS = [f"Council Member Position {n}: District {n}" for n in range(1, 8)] + [
    "Council Member Position 8: At-large",
    "Council Member Position 9: At-large",
]
_GREENSBORO_POSTS = ["Mayor", *["Council Member At Large"] * 3] + [
    f"Council Member District {n}" for n in range(1, 6)
]
_SHELTON_POSTS = [f"Council Member Seat {n}" for n in range(1, 8)]

# The saved runs filed everyone under one default organization. Each split as the city is
# organised, with everyone found but the mayor: the state the mayor's page was buried in.
ORGANIZATION_FIXTURES = {
    "wa/place_seattle": [
        _need("council", 9, 9, ["City Council", *_SEATTLE_COUNCIL_POSTS], []),
        _need("mayor", 1, 0, ["Office of the Mayor", "Mayor"], ["Mayor"]),
    ],
    "nc/place_greensboro": [_need("council", 9, 8, ["City Council", *_GREENSBORO_POSTS], ["Mayor"])],
    # Shelton's mayor is a council member chosen by the council: a membership label, not a post.
    "wa/place_shelton": [
        _need("council", 7, 6, ["City Council", *_SHELTON_POSTS, "Mayor", "Deputy Mayor"], ["Mayor"])
    ],
}


def noise_last_key(link: Link, names: list[str], designations: list[str]) -> tuple:
    """Candidate: today's key exactly, with archive-shaped urls pushed to the back.

    The narrow version of `path_shape_key`, which also counted matching terms and preferred
    short paths and so promoted `Directory.aspx?did=34` over `/126/City-Council` — rewarding an
    opaque CMS path twice. This changes one thing: a url carrying a year or a news/agenda segment
    sorts last, whatever else it scores.
    """
    return (int(_noise(link.url)),) + _pending_sort_key(link, [], names, designations)
