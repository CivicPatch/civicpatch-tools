from statistics import mean
from typing import Callable, Hashable, Iterable, TypeVar

Item = TypeVar("Item")
Key = TypeVar("Key", bound=Hashable)

# Scores this close are the same score; float noise must not read as a change.
SAME_SCORE = 1e-9


def group_by(items: Iterable[Item], key: Callable[[Item], Key]) -> dict[Key, list[Item]]:
    groups: dict[Key, list[Item]] = {}
    for item in items:
        groups.setdefault(key(item), []).append(item)
    return groups


def mean_by_key(rows: Iterable[dict[str, float]]) -> dict[str, float]:
    """Each key averaged over the rows that carry it: an absent key is not a zero."""
    rows = list(rows)
    keys = {key for row in rows for key in row}
    return {key: mean(row[key] for row in rows if key in row) for key in keys}
