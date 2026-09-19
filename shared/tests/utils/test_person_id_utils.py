import uuid

from shared.schemas import Membership, Person
from shared.utils.name_utils import build_canonical_map
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
        "Ruben Gutierrez, Jr.", [], [], [person], canonical_map, identities
    )
    assert len(matches) == 1
    assert matches[0].name == "Ruben Gutierrez, Jr."


def test_resolve_person_id_alias_match():
    """Incoming name matches an alias in identities, not the canonical."""
    person = make_person("Ruben Gutierrez, Jr.")
    identities = {"Ruben Gutierrez, Jr.": ["Ruben Gutierrez Jr."]}
    canonical_map = build_canonical_map([person], identities)

    matches = resolve_person_id(
        "Ruben Gutierrez Jr.", [], [], [person], canonical_map, identities
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
        "Ricardo Richie Rangel Jr", [], [], [person], canonical_map, identities
    )
    assert len(matches) == 1
    assert matches[0].name == "Ricardo Richie Rangel, Jr."


def test_resolve_person_id_no_match():
    person = make_person("Ruben Gutierrez, Jr.")
    identities = {"Ruben Gutierrez, Jr.": []}
    canonical_map = build_canonical_map([person], identities)

    matches = resolve_person_id("John Smith", [], [], [person], canonical_map, identities)
    assert matches == []


def test_resolve_person_id_empty_name():
    person = make_person("Ruben Gutierrez, Jr.")
    identities = {"Ruben Gutierrez, Jr.": []}
    canonical_map = build_canonical_map([person], identities)

    matches = resolve_person_id(None, [], [], [person], canonical_map, identities)
    assert matches == []


def test_resolve_person_id_narrows_by_email():
    """When multiple people share a canonical, email narrows the result."""
    person_a = make_person("Ruben Gutierrez, Jr.", emails=["ruben@ci.laredo.tx.us"])
    person_b = make_person("Ruben Gutierrez, Jr.", emails=["other@ci.laredo.tx.us"])
    identities = {"Ruben Gutierrez, Jr.": []}
    canonical_map = build_canonical_map([person_a, person_b], identities)

    matches = resolve_person_id(
        "Ruben Gutierrez, Jr.",
        [],
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
        "Ruben Gutierrez, Jr.", [], [], [person_a, person_b], canonical_map, identities
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
    assert results[0]["id"] in {"id-a", "id-b"}
    assert {match.id for match in results[0]["matches"]} == {"id-a", "id-b"}


def test_resolve_people_ids_ambiguous_picks_the_closer_name():
    """A default, not a guess: the candidate agreeing on more name components wins."""
    exact = make_person("Ruben Gutierrez, Jr.", id="id-exact")
    looser = make_person("Ruben Gutierrez", id="id-looser")
    identities = {"Ruben Gutierrez, Jr.": ["Ruben Gutierrez"]}

    results = resolve_people_ids(
        [{"id": None, "name": "Ruben Gutierrez, Jr.", "email": None}],
        [exact, looser],
        identities,
    )
    assert results[0]["ambiguous"] is True
    assert results[0]["id"] == "id-exact"


def test_resolve_people_ids_ambiguous_is_deterministic():
    person_a = make_person("John Smith", id="id-a")
    person_b = make_person("John Smith Jr.", id="id-b")
    identities = {"John Smith": ["John Smith Jr."]}
    incoming = [{"id": None, "name": "John Smith", "email": None}]

    forwards = resolve_people_ids(incoming, [person_a, person_b], identities)
    backwards = resolve_people_ids(incoming, [person_b, person_a], identities)

    assert forwards[0]["ambiguous"] is True
    assert forwards[0]["id"] == backwards[0]["id"]


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


def test_resolve_people_ids_matches_on_a_stated_other_name():
    """A sheet row "Jennifer Fisk-Becker" whose volunteer wrote the published "Jenny" beside it."""
    person = make_person("Jenny Fisk-Becker", id="jenny")

    results = resolve_people_ids(
        [{"name": "Jennifer Fisk-Becker", "other_names": ["Jenny Fisk-Becker"]}],
        [person],
        {"Jenny Fisk-Becker": []},
    )
    assert results[0]["id"] == "jenny"


def test_a_stated_other_name_outranks_a_guess_on_the_name():
    guessed = make_person("Jon Smith", id="jon")
    stated = make_person("Johnny Smith", id="johnny")

    matches = resolve_person_id(
        "John Smith",
        ["Johnny Smith"],
        [],
        [guessed, stated],
        build_canonical_map([guessed, stated], {"Jon Smith": [], "Johnny Smith": []}),
        {"Jon Smith": [], "Johnny Smith": []},
    )
    assert [person.id for person in matches] == ["johnny"]


def test_a_stated_other_name_must_match_exactly():
    person = make_person("Jenny Fisk-Becker", id="jenny")

    matches = resolve_person_id(
        "Jennifer Fisk-Becker",
        ["Jenny Fisk"],
        [],
        [person],
        build_canonical_map([person], {"Jenny Fisk-Becker": []}),
        {"Jenny Fisk-Becker": []},
    )
    assert matches == []



def _seated(name, id):
    """On the roster: holds an open membership."""
    return Person(
        id=id,
        name=name,
        memberships=[
            Membership(
                post_id=f"post-{id}",
                role_id="council-member",
                division_ocdid="ocd-division/country:us/state:tx/place:laredo",
                role_label="Council Member",
            )
        ],
        jurisdiction_ocdid=_OCDID,
    )


def _resolve_ids(names, people):
    identities = {person.name: person.other_names for person in people}
    return [result["id"] for result in resolve_people_ids([{"name": n} for n in names], people, identities)]


def test_one_leaving_and_one_arriving_under_a_nickname_are_one_person():
    """Truckee, 2026-09-18: we publish Dave Polivy, the sheet says David."""
    people = [_seated("Dave Polivy", "dave"), _seated("Anna Klovstad", "anna")]

    assert _resolve_ids(["David Polivy", "Anna Klovstad"], people) == ["dave", "anna"]


def test_no_nickname_tie_when_two_absent_people_share_the_surname():
    people = [_seated("Dave Polivy", "dave"), _seated("Donna Polivy", "donna")]

    assert "dave" not in _resolve_ids(["David Polivy"], people)


def test_no_nickname_tie_when_two_arrivals_share_the_surname():
    people = [_seated("Dave Polivy", "dave")]

    assert "dave" not in _resolve_ids(["David Polivy", "Diane Polivy"], people)


def test_no_nickname_tie_to_someone_already_off_the_roster():
    people = [make_person("Dave Polivy", id="dave")]

    assert _resolve_ids(["David Polivy"], people) != ["dave"]


def test_no_nickname_tie_between_names_that_are_not_nicknames():
    people = [_seated("Ricardo Batalla", "ricardo")]

    assert _resolve_ids(["Richard Batalla"], people) != ["ricardo"]
