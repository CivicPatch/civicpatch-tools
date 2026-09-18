"""How soon an ordering reaches the pages that actually produced records.

`mise run frontier-outcomes`. The rank report asks where a url containing "mayor" lands, which is
a proxy somebody made up. This asks the real question: every record kept the `source_url` it came
from, so each link in a saved run either produced people or did not, and an ordering can be scored
on how many fetches it would have taken to reach them.

Two numbers per run, both in fetches:
  first   rank of the earliest productive link — how long until anything is found
  all     rank of the last one — how long until the roster is complete

**The bias to keep in mind.** The links in a saved run are the ones the shipped order chose to
discover, and outcomes exist only for pages it chose to fetch. Reordering that set is a fair
comparison between keys; it cannot tell you about a page nobody ever looked at.
"""

import os
import pathlib

from tests.unit.runners.frontier_replay import (
    all_links,
    load_frontier,
    organization_first_key,
    noise_last_key,
    path_shape_key,
    productive_urls,
    research_signals,
    saved_contexts,
)
from runners.people_collector.utils.link_discovery import _pending_sort_key
from shared.utils.url_utils import canonical_url

KEYS = {
    "shipped": _pending_sort_key,
    "organization_first": organization_first_key,
    "path_shape": path_shape_key,
    "noise_last": noise_last_key,
}


def _ranks(context_path: pathlib.Path, key) -> tuple[int, int] | None:
    """Where the productive links land under this ordering, 1-based."""
    productive = productive_urls(context_path)
    if not productive:
        return None
    frontier = load_frontier(context_path)
    names, designations = research_signals(context_path)
    ordered_links = sorted(
        all_links(frontier),
        key=lambda link: key(link, list(names), list(designations)),
    )
    ranks = [
        position
        for position, link in enumerate(ordered_links, start=1)
        if canonical_url(link.url) in productive
    ]
    return (min(ranks), max(ranks)) if ranks else None


def report() -> None:
    contexts = saved_contexts()
    scored = [(path, _ranks(path, KEYS["shipped"])) for path in contexts]
    scored = [(path, ranks) for path, ranks in scored if ranks]
    if not scored:
        print("No saved run has a productive link to score against.")
        return

    names = [name for name in os.environ.get("FRONTIER_KEYS", "").split(",") if name] or list(KEYS)
    print(f"{'jurisdiction':34} " + "  ".join(f"{name:>20}" for name in names))
    print(f"{'':34} " + "  ".join(f"{'first / all':>20}" for _ in names))
    totals = {name: [0, 0] for name in names}
    for path, _ in scored:
        cells = []
        for name in names:
            ranks = _ranks(path, KEYS[name])
            assert ranks
            first, last = ranks
            totals[name][0] += first
            totals[name][1] += last
            cells.append(f"{first:>9} / {last:<8}")
        print(f"{path.parents[2].name + '/' + path.parents[0].name:34} " + "  ".join(cells))

    print()
    runs = len(scored)
    print(f"{'mean over ' + str(runs) + ' runs':34} " + "  ".join(
        f"{totals[name][0] / runs:>9.1f} / {totals[name][1] / runs:<8.1f}" for name in names
    ))
    print("\nLower is better: fetches until the first record, and until the last.")


if __name__ == "__main__":
    report()
