from unittest.mock import MagicMock

import pytest

from core.people_roster import (
    identified,
    named_like_a_person,
    roster_from_rows,
    with_fallback_url,
)
from shared.schemas import Person, Role, RoleConfig, RoleStatus
from shared.utils.official_fields import office_name_to_labels
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


def _official(name: str, office_name: str, division_ocdid: str | None = None) -> dict:
    return {
        "name": name,
        "office": {"name": office_name, "division_ocdid": division_ocdid},
        "jurisdiction_ocdid": JURISDICTION,
        "source_urls": [],
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


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
def test_officials_pass_through_untouched():
    """The shape the pipeline still sends. Nothing is reconciled — it already was."""
    kept = _reconcile([_official("Ann Lee", "Council Member Place 2", f"{BASE}/ward:east")])
    assert kept[0]["office"]["name"] == "Council Member Place 2"
    assert kept[0]["office"]["division_ocdid"] == f"{BASE}/ward:east"


@pytest.mark.unit
def test_a_field_official_does_not_model_survives_the_passthrough():
    """`order_official_fields` exists because rosters carry fields the model does not declare.
    Validating a row on the way through would drop every one of them."""
    row = _official("Ann Lee", "Mayor")
    row["some_field_we_do_not_model"] = "keep me"
    kept = _reconcile([row])
    assert kept[0]["some_field_we_do_not_model"] == "keep me"


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
    assert sorted(office_name_to_labels(kept[0]["office"]["name"])) == [
        "Council Member Place 2",
        "Mayor Pro-Tem",
    ]


@pytest.mark.unit
def test_the_rendered_office_name_splits_back_into_its_labels():
    """The join is lossy but reversible by the same delimiter every reader already uses, so
    a consumer still speaking `Official` sees what a record-shaped one would."""
    kept = _reconcile(
        [
            _record("Ann Lee", "Council Member Place 2"),
            _record("Ann Lee", "Mayor Pro-Tem"),
        ]
    )
    labels = office_name_to_labels(kept[0]["office"]["name"])
    assert len(labels) == 2
    assert all(" - " not in label for label in labels)


@pytest.mark.unit
def test_the_division_comes_back_out_of_the_verbatim_label():
    """The property that made it safe to stop passing `division_ocdid` separately: a record's
    label is untouched, so it still names the area."""
    kept = _reconcile([_record("Ann Lee", "Council Member (East Ward)")])
    assert kept[0]["office"]["division_ocdid"] == f"{BASE}/ward:east"


@pytest.mark.unit
def test_a_label_naming_no_area_gets_the_jurisdictions_own_division():
    kept = _reconcile([_record("Ann Lee", "Mayor")])
    assert kept[0]["office"]["division_ocdid"] == BASE


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


@pytest.mark.unit
def test_an_already_merged_roster_has_no_records_behind_it():
    """Nothing to keep: the sightings were merged before it arrived."""
    assert _records_behind([_official("Ann Lee", "Mayor")]) == {}
