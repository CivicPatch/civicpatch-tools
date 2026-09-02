"""`sort_people` — the order a rendered roster is read in.

Moved from the pipeline with the function on 2026-08-21.
"""

from shared.schemas import DerivedPerson
from shared.utils.people_utils import sort_people
from shared.utils.taxonomy import Taxonomy


# Keys are stored in lookup form, so "at-large" is keyed "at large".
_SORT_TAXONOMY = Taxonomy(
    # The parser resolves a role out of the whole label, so it needs aliases where the old
    # two-bag code could take an already-canonical role string.
    # "Trustee", not "Seat": a role named "Seat" collides with the `seat` designation
    # keyword, so the label reads "Seat Seat 10" and the test measures the collision
    # rather than the ordering it is named for.
    role_aliases={"mayor": "Mayor", "council": "Council", "trustee": "Trustee"},
    designation_aliases={"seat": "seat", "ward": "ward", "at large": "at-large"},
    role_priority={"Mayor": 0, "Council": 1, "Trustee": 2},
    designation_priority={"seat": 0, "ward": 1, "at large": 2},
)


def _person(name: str, labels: list[str]) -> DerivedPerson:
    return DerivedPerson(
        name=name,
        labels=labels,
        updated_at="2024-01-01",
        jurisdiction_ocdid="ocd-jurisdiction/country:us/state:xy/place:abc",
        source_urls=[],
    )


# --- sort_people ---


def test_sort_people_priority_and_numeric():
    people = [
        _person("Alice", ["Council Ward 2"]),
        _person("Bob", ["Mayor At-Large"]),
        _person("Carol", ["Trustee Seat 10"]),
        _person("Dave", ["Trustee Seat 1"]),
        _person("Eve", ["Council Ward 1"]),
    ]
    sorted_people = sort_people(people, _SORT_TAXONOMY)
    assert [p.name for p in sorted_people] == ["Bob", "Eve", "Alice", "Dave", "Carol"]


def test_sort_people_uses_the_highest_priority_of_several_labels():
    """One label per office, so a person holding two sorts by the highest-priority one."""
    people = [
        _person("Alice", ["Council Ward 1"]),
        _person("Bob", ["Council Ward 2", "Mayor At-Large"]),
    ]
    assert [p.name for p in sort_people(people, _SORT_TAXONOMY)] == ["Bob", "Alice"]
