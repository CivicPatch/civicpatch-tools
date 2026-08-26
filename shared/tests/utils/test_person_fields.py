"""The key order of a person in a data file.

Every assertion here is about a file humans read and git diffs, so a change in order is a
change in every file at once.
"""

from shared.utils.person_fields import PERSON_FIELD_ORDER, order_person_fields

# A second, independent copy of the order — deliberately not imported from the module under
# test. Two literals that must agree is the whole point: changing the layout of every data
# file in open-data should take two edits and a failing test, never one edit.
EXPECTED_ORDER = [
    "name",
    "other_names",
    "phones",
    "emails",
    "urls",
    "start_date",
    "end_date",
    "office",
    "image",
    "jurisdiction_ocdid",
    "cdn_image",
    "source_urls",
    "updated_at",
    "id",
]


def _person(**overrides):
    return {
        "name": "Alice Adams",
        "other_names": [],
        "phones": [],
        "emails": [],
        "urls": [],
        "start_date": None,
        "end_date": None,
        "office": {"name": "Mayor", "division_ocdid": None},
        "image": None,
        "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:x/government",
        "cdn_image": None,
        "source_urls": [],
        "updated_at": "2025-11-18T19:49:42+00:00",
        "id": "a",
        **overrides,
    }


def test_field_order_matches_the_on_disk_contract():
    assert list(PERSON_FIELD_ORDER) == EXPECTED_ORDER


def test_office_is_still_in_the_order():
    """It goes when the proposed roster stops carrying it, and that is a data-file change
    to make on purpose — not one to notice after the fact."""
    assert "office" in PERSON_FIELD_ORDER


def test_id_first_entry_is_reordered():
    entry = {"id": "a", **{k: v for k, v in _person().items() if k != "id"}}
    assert list(order_person_fields(entry)) == EXPECTED_ORDER


def test_legacy_pipeline_order_is_reordered():
    person = _person()
    trailing = ["start_date", "end_date", "other_names"]
    entry = {k: person[k] for k in person if k not in trailing}
    for key in trailing:
        entry[key] = person[key]
    assert list(order_person_fields(entry)) == EXPECTED_ORDER


def test_already_ordered_entry_is_unchanged():
    entry = _person()
    assert order_person_fields(entry) == entry
    assert list(order_person_fields(entry)) == list(entry)


def test_values_are_the_original_objects():
    entry = _person(phones=["(916) 808-5300"])
    ordered = order_person_fields(entry)
    assert ordered["phones"] is entry["phones"]
    assert ordered["office"] is entry["office"]


def test_absent_keys_are_not_invented():
    ordered = order_person_fields({"id": "a", "name": "Alice Adams"})
    assert list(ordered) == ["name", "id"]


def test_undeclared_keys_are_kept_at_the_end():
    entry = {"id": "a", "legacy_note": "keep me", "name": "Alice Adams"}
    assert list(order_person_fields(entry)) == ["name", "id", "legacy_note"]
