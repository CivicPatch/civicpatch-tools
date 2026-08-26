from unittest.mock import MagicMock

import pytest

from core.people_roster import (
    identified,
    named_like_a_person,
    roster_from_rows,
    roster_from_sightings,
    reviewer_source_records,
    with_fallback_url,
)
from shared.schemas import Person, PersonRecord, Role, RoleConfig, RoleStatus
from shared.utils.taxonomy import build_taxonomy

# Pure — rows and a taxonomy in, a roster out. The ingest that calls this lives in
# services/people_collector.py.

# Pure — rows and a taxonomy in, officials out. The ingest that calls this lives in
# services/people_collector.py.

JURISDICTION = "ocd-jurisdiction/country:us/state:tx/place:alpha/government"
BASE = "ocd-division/country:us/state:tx/place:alpha"


def _role(id_, label, aliases, priority):
    return Role(
        id=id_,
        label=label,
        status=RoleStatus.ACTIVE,
        aliases=aliases,
        priority=priority,
        is_unique=False,
    )


TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            _role("mayor", "Mayor", [], 10),
            _role("mayor-pro-tem", "Mayor Pro Tem", ["Mayor Pro-Tem"], 50),
            _role("council-member", "Council Member", ["Councilman"], 500),
        ]
    )
)


def _record(name: str, label: str, **fields) -> dict:
    return {"name": name, "label": label, "source_url": "https://alpha.gov/council", **fields}


def _reconcile(rows: list[dict], identities=None):
    roster, _records = roster_from_rows(
        rows, identities or {}, TAXONOMY, JURISDICTION, MagicMock()
    )
    return roster


def _records_behind(rows: list[dict], identities=None):
    _roster, records = roster_from_rows(
        rows, identities or {}, TAXONOMY, JURISDICTION, MagicMock()
    )
    return records


@pytest.mark.unit
def test_no_rows_is_not_an_error():
    assert _reconcile([]) == []


@pytest.mark.unit
def test_two_sightings_of_one_person_become_one_official():
    kept = _reconcile(
        [
            _record("Ann Lee", "Council Member Place 2", phone="(512) 978-2100"),
            _record("Ann Lee", "Mayor Pro-Tem", email="ann@alpha.gov"),
        ]
    )
    assert len(kept) == 1
    assert kept[0]["phones"] == ["(512) 978-2100"]
    assert kept[0]["emails"] == ["ann@alpha.gov"]
    assert sorted(kept[0]["labels"]) == ["Council Member Place 2", "Mayor Pro-Tem"]


@pytest.mark.unit
def test_labels_are_carried_verbatim_and_office_is_not_rendered():
    """Was `test_the_rendered_office_name_splits_back_into_its_labels`, which asserted the
    join could be undone; then that the list sat beside it. Now `office` is not rendered at
    all — the list is the only answer, which is what removing the join means."""
    kept = _reconcile(
        [
            _record("Ann Lee", "Council Member Place 2"),
            _record("Ann Lee", "Mayor Pro-Tem"),
        ]
    )
    assert sorted(kept[0]["labels"]) == ["Council Member Place 2", "Mayor Pro-Tem"]
    assert "office" not in kept[0]


@pytest.mark.unit
def test_the_division_comes_back_out_of_the_verbatim_label():
    """The property that made it safe to stop passing `division_ocdid` separately: a record's
    label is untouched, so it still names the area."""
    kept = _reconcile([_record("Ann Lee", "Council Member (East Ward)")])
    assert kept[0]["division_ocdid"] == f"{BASE}/ward:east"


@pytest.mark.unit
def test_a_label_naming_no_area_gets_the_jurisdictions_own_division():
    kept = _reconcile([_record("Ann Lee", "Mayor")])
    assert kept[0]["division_ocdid"] == BASE


@pytest.mark.unit
def test_a_person_no_role_matches_stays_on_the_roster():
    """This used to drop them. The drop could not tell an out-of-scope title from one the
    taxonomy is missing, and recorded neither — scope is `posts._is_tracked` now, decided when
    the post is minted."""
    kept = _reconcile([_record("Ann Lee", "City Attorney")])
    assert [p["name"] for p in kept] == ["Ann Lee"]


@pytest.mark.unit
def test_identities_keep_two_people_sharing_a_surname_apart():
    """The prior cp.org reads off its own people, or off the submitted run context when it
    has none. Without it these two merge."""
    rows = [
        _record("Martin Cantu, Jr.", "Mayor"),
        _record("Martin C. Cantu, Sr.", "Council Member Place 3"),
    ]
    identities = {"Martin Cantu, Jr.": [], "Martin C. Cantu, Sr.": []}
    kept = _reconcile(rows, identities)
    assert len(kept) == 2


# --- identified: the id and aliases cp.org resolved for a roster entry ---


def _person(name: str, other_names=None) -> Person:
    return Person(
        name=name, other_names=other_names or [], jurisdiction_ocdid=JURISDICTION
    )


def _resolution(id_: str, person=None, ambiguous=False) -> dict:
    return {"id": id_, "person": person, "ambiguous": ambiguous, "duplicate_match": False}


@pytest.mark.unit
def test_the_resolved_id_lands_on_the_entry():
    entry = identified({"name": "Ann Lee"}, _resolution("abc-123", _person("Ann Lee")))
    assert entry["id"] == "abc-123"


@pytest.mark.unit
def test_a_matched_persons_aliases_carry_forward():
    """Human-added `other_names` are the durable signal that steers the next run's name
    matching, so a scrape must not clobber them."""
    entry = identified(
        {"name": "Ann Lee", "other_names": ["Annie"]},
        _resolution("abc-123", _person("Ann Lee", ["A. Lee"])),
    )
    assert entry["other_names"] == ["Annie", "A. Lee"]


@pytest.mark.unit
def test_a_renamed_person_keeps_both_names_as_aliases():
    entry = identified(
        {"name": "Ann Marie Lee"}, _resolution("abc-123", _person("Ann Lee"))
    )
    assert entry["other_names"] == ["Ann Marie Lee", "Ann Lee"]


@pytest.mark.unit
def test_an_unmatched_entry_gets_an_id_and_keeps_its_own_names():
    """Nothing confirmed to carry aliases forward from."""
    entry = identified(
        {"name": "Ann Lee", "other_names": ["Annie"]}, _resolution("new-id")
    )
    assert entry["id"] == "new-id"
    assert entry["other_names"] == ["Annie"]


@pytest.mark.unit
def test_an_ambiguous_match_carries_nothing_forward():
    """Two candidates means guessing would put somebody else's aliases on this person."""
    entry = identified(
        {"name": "Ann Lee", "other_names": ["Annie"]},
        _resolution("a:b", [_person("Ann Lee", ["A. Lee"])], ambiguous=True),
    )
    assert entry["other_names"] == ["Annie"]


# --- what a roster entry has to look like to be a person at all ---


@pytest.mark.unit
def test_a_one_word_name_is_not_a_person():
    """A label the extractor read as a person — "Vacant", a heading, a bare role."""
    assert named_like_a_person(_person("Vacant")) is False
    assert named_like_a_person(_person("Ann Lee")) is True


@pytest.mark.unit
def test_someone_with_no_url_of_their_own_gets_the_page_they_were_found_on():
    person = _person("Ann Lee")
    person.source_urls = ["https://alpha.gov/council"]
    assert with_fallback_url(person).urls == ["https://alpha.gov/council"]


@pytest.mark.unit
def test_a_url_of_their_own_is_not_replaced():
    person = _person("Ann Lee")
    person.urls = ["https://alpha.gov/ann"]
    person.source_urls = ["https://alpha.gov/council"]
    assert with_fallback_url(person).urls == ["https://alpha.gov/ann"]


@pytest.mark.unit
def test_nothing_to_fall_back_to_leaves_the_person_alone():
    person = _person("Ann Lee")
    assert with_fallback_url(person) is person


# --- the records behind each person, for the evidence table ---


@pytest.mark.unit
def test_every_sighting_is_kept_against_the_person_it_reconciled_into():
    """`source_records` stores one row per sighting, so the merge has to say which rows it
    merged — a person alone cannot say which page gave it a phone number."""
    records = _records_behind(
        [
            _record("Ann Lee", "Council Member Place 2", phone="(512) 978-2100"),
            _record("Ann Lee", "Mayor Pro-Tem", email="ann@alpha.gov"),
        ]
    )
    assert [record["label"] for record in records["Ann Lee"]] == [
        "Council Member Place 2",
        "Mayor Pro-Tem",
    ]


# --- reading the roster back out of stored sightings ---


def _sighting(person_id: str, name: str, label: str, **fields) -> dict:
    return {
        "person_id": person_id,
        "name": name,
        "label": label,
        "source_url": "https://alpha.gov/council",
        "image": None,
        "cdn_image": None,
        **fields,
    }


def _roster_back(sightings: list[dict], published=None):
    return roster_from_sightings(
        sightings, published or {}, TAXONOMY, JURISDICTION, MagicMock()
    )


@pytest.mark.unit
def test_stored_sightings_rebuild_the_roster_ingest_produced():
    rows = [
        _record("Ann Lee", "Council Member Place 2", phone="(512) 978-2100"),
        _record("Ann Lee", "Mayor Pro-Tem", email="ann@alpha.gov"),
    ]
    at_ingest = _reconcile(rows)
    read_back = _roster_back(
        [_sighting("p1", row["name"], row["label"], **{k: v for k, v in row.items()
                                                      if k not in ("name", "label")})
         for row in rows]
    )

    assert len(read_back) == 1
    assert read_back[0]["labels"] == at_ingest[0]["labels"]
    assert read_back[0]["division_ocdid"] == at_ingest[0]["division_ocdid"]
    assert read_back[0]["phones"] == at_ingest[0]["phones"]
    assert read_back[0]["emails"] == at_ingest[0]["emails"]


@pytest.mark.unit
def test_grouping_is_read_from_the_identity_not_guessed_again():
    """Two spellings the name matcher would have to reunite. It does not run here — the
    scrape already decided they are one person, and that answer is stored."""
    kept = _roster_back(
        [
            _sighting("p1", "Bob Kettle", "Mayor"),
            _sighting("p1", "Robert Kettle", "Mayor"),
        ]
    )
    assert len(kept) == 1
    assert kept[0]["id"] == "p1"


@pytest.mark.unit
def test_two_identities_stay_two_people_even_under_one_name():
    """The mirror of the above: the identity splits as well as joins."""
    kept = _roster_back(
        [_sighting("p1", "Ann Lee", "Mayor"), _sighting("p2", "Ann Lee", "Council Member")]
    )
    assert sorted(person["id"] for person in kept) == ["p1", "p2"]


@pytest.mark.unit
def test_the_published_name_wins_over_what_the_pages_spelled():
    """`published` is the read-time half of `identities` — the human's answer, taken from
    `people` rather than from the run context."""
    kept = _roster_back(
        [_sighting("p1", "Katie B. Wilson", "Council Member") for _ in range(3)],
        published={"p1": _person("Katie Wilson")},
    )
    assert kept[0]["name"] == "Katie Wilson"
    assert kept[0]["other_names"] == ["Katie B. Wilson"]


@pytest.mark.unit
def test_confirmed_aliases_survive_a_scrape_that_never_saw_them():
    """Every sighting spells him "Bob Kettle"; `["Robert Kettle"]` is a human's answer living
    on the person. At ingest `identified` carries it forward — the read groups by a stored id
    and does no matching, so without this it comes back empty."""
    kept = _roster_back(
        [_sighting("p1", "Bob Kettle", "Council Member")],
        published={"p1": _person("Bob Kettle", ["Robert Kettle"])},
    )
    assert kept[0]["other_names"] == ["Robert Kettle"]


@pytest.mark.unit
def test_a_person_nobody_has_published_takes_the_most_frequent_spelling():
    kept = _roster_back(
        [
            _sighting("p1", "Bob Kettle", "Mayor"),
            _sighting("p1", "Robert Kettle", "Mayor"),
            _sighting("p1", "Bob Kettle", "Mayor"),
        ]
    )
    assert kept[0]["name"] == "Bob Kettle"


@pytest.mark.unit
def test_the_photo_and_its_cdn_url_come_from_the_same_sighting():
    """Merging them independently can credit one page for a photo served from another."""
    kept = _roster_back(
        [
            _sighting("p1", "Ann Lee", "Mayor",
                      image="https://alpha.gov/a.png", cdn_image="https://cdn/a.png"),
            _sighting("p1", "Ann Lee", "Council Member",
                      image="https://alpha.gov/a.png", cdn_image="https://cdn/a.png"),
            _sighting("p1", "Ann Lee", "Mayor Pro-Tem",
                      image="https://alpha.gov/b.png", cdn_image="https://cdn/b.png"),
        ]
    )
    assert kept[0]["image"] == "https://alpha.gov/a.png"
    assert kept[0]["cdn_image"] == "https://cdn/a.png"


@pytest.mark.unit
def test_no_sightings_is_not_an_error():
    assert _roster_back([]) == []


# --- a person the reviewer added by hand ---


@pytest.mark.unit
def test_an_added_person_becomes_one_record_per_page():
    """A row is what one page said about one person, so a reviewer listing two sources saw
    them twice. `label` is empty: they pick a post and never type a label — `labels` are what
    a source said, and are never edited."""
    added = {
        "name": "Ann Lee",
        "source_urls": ["https://alpha.gov/council", "https://alpha.gov/directory"],
    }

    assert reviewer_source_records(added) == [
        PersonRecord(name="Ann Lee", label="", source_url="https://alpha.gov/council"),
        PersonRecord(name="Ann Lee", label="", source_url="https://alpha.gov/directory"),
    ]


@pytest.mark.unit
def test_one_page_listed_twice_is_still_one_record():
    added = {
        "name": "Ann Lee",
        "source_urls": ["https://alpha.gov/council", "https://alpha.gov/council"],
    }
    assert len(reviewer_source_records(added)) == 1


@pytest.mark.unit
def test_nothing_is_recorded_without_somewhere_it_came_from():
    """`source_url` is NOT NULL because provenance is what a sighting is for. The editor makes
    it required, so this is the last guard rather than the only one."""
    assert reviewer_source_records({"name": "Ann Lee", "source_urls": []}) == []
    assert reviewer_source_records({"name": "", "source_urls": ["https://alpha.gov"]}) == []


@pytest.mark.unit
def test_only_the_identifying_columns_are_evidence():
    """Everything else the reviewer typed is a claim, recorded by `stated_from_edit`. Copying
    it here too would make the sighting a second, competing answer."""
    record = reviewer_source_records({
        "name": "Ann Lee",
        "source_urls": ["https://alpha.gov/council"],
        "phones": ["(512) 978-2100"],
        "image": "https://alpha.gov/ann.png",
    })[0]
    assert record.phone is None and record.image is None
