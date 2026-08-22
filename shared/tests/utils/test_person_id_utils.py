import uuid

import pytest

from shared.schemas import Person
from shared.utils.name_utils import best_identity_match, build_canonical_map
from shared.utils.person_id_utils import resolve_people_ids, resolve_person_id

_OCDID = "ocd-jurisdiction/country:us/state:tx/place:laredo/government"


# Real people, not mocks: a mock answers for any attribute, which is how a lookup on a field
# `Person` does not have went unnoticed.
def make_person(name, other_names=None, emails=None, id=None):
    return Person(
        id=id or str(uuid.uuid4()),
        name=name,
        other_names=other_names or [],
        emails=emails or [],
        jurisdiction_ocdid=_OCDID,
    )


# --- resolve_person_id ---


def test_resolve_person_id_exact_match():
    person = make_person("Ruben Gutierrez, Jr.")
    identities = {"Ruben Gutierrez, Jr.": ["Ruben Gutierrez Jr."]}
    canonical_map = build_canonical_map([person], identities)

    matches = resolve_person_id(
        "Ruben Gutierrez, Jr.", [], [person], canonical_map, identities
    )
    assert len(matches) == 1
    assert matches[0].name == "Ruben Gutierrez, Jr."


def test_resolve_person_id_alias_match():
    """Incoming name matches an alias in identities, not the canonical."""
    person = make_person("Ruben Gutierrez, Jr.")
    identities = {"Ruben Gutierrez, Jr.": ["Ruben Gutierrez Jr."]}
    canonical_map = build_canonical_map([person], identities)

    matches = resolve_person_id(
        "Ruben Gutierrez Jr.", [], [person], canonical_map, identities
    )
    assert len(matches) == 1
    assert matches[0].name == "Ruben Gutierrez, Jr."


def test_resolve_person_id_fuzzy_match_via_identity():
    """Incoming name not in canonical map but fuzzy-matches an identity."""
    person = make_person("Ricardo Richie Rangel, Jr.")
    identities = {"Ricardo Richie Rangel, Jr.": ["Ricardo Richie Rangel Jr."]}
    canonical_map = build_canonical_map([person], identities)

    # Incoming name is a variant not literally in the map
    matches = resolve_person_id(
        "Ricardo Richie Rangel Jr", [], [person], canonical_map, identities
    )
    assert len(matches) == 1
    assert matches[0].name == "Ricardo Richie Rangel, Jr."


def test_resolve_person_id_no_match():
    person = make_person("Ruben Gutierrez, Jr.")
    identities = {"Ruben Gutierrez, Jr.": []}
    canonical_map = build_canonical_map([person], identities)

    matches = resolve_person_id("John Smith", [], [person], canonical_map, identities)
    assert matches == []


def test_resolve_person_id_empty_name():
    person = make_person("Ruben Gutierrez, Jr.")
    identities = {"Ruben Gutierrez, Jr.": []}
    canonical_map = build_canonical_map([person], identities)

    matches = resolve_person_id(None, [], [person], canonical_map, identities)
    assert matches == []


def test_resolve_person_id_narrows_by_email():
    """When multiple people share a canonical, email narrows the result."""
    person_a = make_person("Ruben Gutierrez, Jr.", emails=["ruben@ci.laredo.tx.us"])
    person_b = make_person("Ruben Gutierrez, Jr.", emails=["other@ci.laredo.tx.us"])
    identities = {"Ruben Gutierrez, Jr.": []}
    canonical_map = build_canonical_map([person_a, person_b], identities)

    matches = resolve_person_id(
        "Ruben Gutierrez, Jr.",
        ["ruben@ci.laredo.tx.us"],
        [person_a, person_b],
        canonical_map,
        identities,
    )
    assert len(matches) == 1
    assert matches[0].emails == ["ruben@ci.laredo.tx.us"]


def test_resolve_person_id_ambiguous_without_email():
    """Multiple matches with no email returns all."""
    person_a = make_person("Ruben Gutierrez, Jr.", emails=["ruben@ci.laredo.tx.us"])
    person_b = make_person("Ruben Gutierrez, Jr.", emails=["other@ci.laredo.tx.us"])
    identities = {"Ruben Gutierrez, Jr.": []}
    canonical_map = build_canonical_map([person_a, person_b], identities)

    matches = resolve_person_id(
        "Ruben Gutierrez, Jr.", [], [person_a, person_b], canonical_map, identities
    )
    assert len(matches) == 2


# --- resolve_people_ids ---


def test_resolve_people_ids_single_match():
    person = make_person("Ruben Gutierrez, Jr.", id="abc-123")
    identities = {"Ruben Gutierrez, Jr.": ["Ruben Gutierrez Jr."]}

    results = resolve_people_ids(
        [{"id": None, "name": "Ruben Gutierrez Jr.", "email": None}],
        [person],
        identities,
    )
    assert len(results) == 1
    assert results[0]["id"] == "abc-123"
    assert results[0]["ambiguous"] is False


def test_resolve_people_ids_no_match_generates_id():
    person = make_person("Ruben Gutierrez, Jr.")
    identities = {"Ruben Gutierrez, Jr.": []}

    results = resolve_people_ids(
        [{"id": None, "name": "John Smith", "email": None}],
        [person],
        identities,
    )
    assert len(results) == 1
    assert results[0]["person"] is None
    assert results[0]["ambiguous"] is False
    assert results[0]["id"]  # generated uuid


def test_resolve_people_ids_no_match_preserves_incoming_id():
    person = make_person("Ruben Gutierrez, Jr.")
    identities = {"Ruben Gutierrez, Jr.": []}
    incoming_id = str(uuid.uuid4())

    results = resolve_people_ids(
        [{"id": incoming_id, "name": "John Smith", "email": None}],
        [person],
        identities,
    )
    assert results[0]["id"] == incoming_id


def test_resolve_people_ids_ambiguous():
    person_a = make_person("Ruben Gutierrez, Jr.", id="id-a")
    person_b = make_person("Ruben Gutierrez, Jr.", id="id-b")
    identities = {"Ruben Gutierrez, Jr.": []}

    results = resolve_people_ids(
        [{"id": None, "name": "Ruben Gutierrez, Jr.", "email": None}],
        [person_a, person_b],
        identities,
    )
    assert results[0]["ambiguous"] is True
    assert "id-a" in results[0]["id"]
    assert "id-b" in results[0]["id"]


def test_resolve_people_ids_multiple_people():
    person_a = make_person("Ruben Gutierrez, Jr.", id="id-a")
    person_b = make_person("Ricardo Richie Rangel, Jr.", id="id-b")
    identities = {
        "Ruben Gutierrez, Jr.": ["Ruben Gutierrez Jr."],
        "Ricardo Richie Rangel, Jr.": ["Ricardo Richie Rangel Jr."],
    }

    results = resolve_people_ids(
        [
            {"id": None, "name": "Ruben Gutierrez Jr.", "email": None},
            {"id": None, "name": "Ricardo Richie Rangel Jr.", "email": None},
        ],
        [person_a, person_b],
        identities,
    )
    assert results[0]["id"] == "id-a"
    assert results[1]["id"] == "id-b"


def test_resolve_people_ids_never_hands_out_the_same_id_twice():
    # A source page that lists one official twice — under two committees, say —
    # sends two entries that resolve to the same existing person. Reusing the id
    # would collapse the pair downstream, where people are keyed by id, and drop
    # one of them without ever showing it.
    person = make_person("Ruben Gutierrez, Jr.", id="abc-123")
    identities = {"Ruben Gutierrez, Jr.": []}

    results = resolve_people_ids(
        [
            {"id": None, "name": "Ruben Gutierrez, Jr.", "email": None},
            {"id": None, "name": "Ruben Gutierrez, Jr.", "email": None},
        ],
        [person],
        identities,
    )

    assert results[0]["id"] == "abc-123"
    assert results[0]["duplicate_match"] is False
    assert results[1]["id"] != "abc-123"
    assert results[1]["duplicate_match"] is True
    # The second is not claimed to be the existing person, because it is not
    # known to be — a reviewer decides.
    assert results[1]["person"] is None


def test_resolve_people_ids_collision_via_alias():
    # Merging records the absorbed name as an alias, so a later scrape returning
    # both names resolves both to the survivor. Same collision, different route.
    person = make_person("Robert Smith", id="survivor-1")
    identities = {"Robert Smith": ["Bob Smith"]}

    results = resolve_people_ids(
        [
            {"id": None, "name": "Robert Smith", "email": None},
            {"id": None, "name": "Bob Smith", "email": None},
        ],
        [person],
        identities,
    )

    assert results[0]["id"] == "survivor-1"
    assert results[1]["id"] != "survivor-1"
    assert results[1]["duplicate_match"] is True


def test_resolve_people_ids_distinct_people_keep_their_matches():
    # The guard must not fire on ordinary batches: two different officials each
    # matching their own record both keep the id they matched.
    person_a = make_person("Ruben Gutierrez, Jr.", id="id-a")
    person_b = make_person("Ricardo Richie Rangel, Jr.", id="id-b")
    identities = {"Ruben Gutierrez, Jr.": [], "Ricardo Richie Rangel, Jr.": []}

    results = resolve_people_ids(
        [
            {"id": None, "name": "Ruben Gutierrez, Jr.", "email": None},
            {"id": None, "name": "Ricardo Richie Rangel, Jr.", "email": None},
        ],
        [person_a, person_b],
        identities,
    )

    assert [r["id"] for r in results] == ["id-a", "id-b"]
    assert all(r["duplicate_match"] is False for r in results)
