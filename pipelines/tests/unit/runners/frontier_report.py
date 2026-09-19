"""Where each organization's pages rank in the queue every saved run left behind.

`mise run frontier-report`. No network, no LLM, no database: it replays `data_source`'s saved
frontiers through the shipped sort key and prints where a mayor-ish page lands. That is the
number the org-aware plan's deferred item 10 is waiting on — the reference bias was measured on
one run before seeds existed, and nobody has checked it since.

Prints rather than asserts. A crawl that ranks the mayor's office tenth is not a broken build,
it is a fact to decide against.
"""

import os
import pathlib

from tests.unit.runners.frontier_replay import (
    ORGANIZATION_FIXTURES,
    organization_first_key,
    load_frontier,
    noise_last_key,
    path_shape_key,
    ordered,
    pending,
    rank_of,
    shipped_key,
    research_signals,
    saved_contexts,
    url_contains,
)

# What an organization's own page tends to look like in a url. Crude on purpose: the saved runs predate
# any per-organization labelling, so the url is the only signal available to ask the question at all.
ORGANIZATION_FRAGMENTS = ("mayor", "council", "trustee", "alderman", "selectboard", "supervisor")


CANDIDATES = {
    "organization_first": organization_first_key,
    "path_shape": path_shape_key,
    "noise_last": noise_last_key,
}
# Which candidate the report compares today's order against: `FRONTIER_CANDIDATE=path_shape`.
CANDIDATE = os.environ.get("FRONTIER_CANDIDATE", "organization_first")


def _jurisdiction(path: pathlib.Path) -> str:
    return f"{path.parents[2].name}/{path.parents[0].name}"


def report() -> int:
    contexts = saved_contexts()
    if not contexts:
        print("No saved pipeline_run_context.json under data_source.")
        return 0

    print(f"{'jurisdiction':38} {'pending':>7}  rank today → with {CANDIDATE} key")
    interesting = 0
    for path in contexts:
        frontier = load_frontier(path)
        waiting = pending(frontier)
        if not waiting:
            continue
        names, designations = research_signals(path)
        needs = ORGANIZATION_FIXTURES.get(_jurisdiction(path), [])
        today = ordered(frontier, names, designations, key=shipped_key(needs))
        candidate = ordered(frontier, names, designations, key=CANDIDATES[CANDIDATE])
        found = {
            fragment: (rank, rank_of(candidate, url_contains(fragment)))
            for fragment in ORGANIZATION_FRAGMENTS
            if (rank := rank_of(today, url_contains(fragment)))
        }
        if not found:
            continue
        interesting += 1
        summary = ", ".join(
            f"{fragment} #{now}→#{then}" if now != then else f"{fragment} #{now}"
            for fragment, (now, then) in sorted(found.items(), key=lambda kv: kv[1][0])
        )
        print(f"{_jurisdiction(path):38} {len(waiting):>7}  {summary}")
    print(f"\n{interesting} of {len(contexts)} saved runs have a pending organization page.")
    return interesting


if __name__ == "__main__":
    report()
