from shared.utils.official_fields import OFFICIAL_FIELD_ORDER, order_official_fields

# Pinned deliberately, not derived from the model: reordering `Official`'s fields silently
# rewrites the key order of every person in every data file, so it must fail a test first.
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
    assert list(OFFICIAL_FIELD_ORDER) == EXPECTED_ORDER


def test_id_first_entry_is_reordered():
    entry = {"id": "a", **{k: v for k, v in _person().items() if k != "id"}}
    assert list(order_official_fields(entry)) == EXPECTED_ORDER


def test_legacy_pipeline_order_is_reordered():
    person = _person()
    trailing = ["start_date", "end_date", "other_names"]
    entry = {k: person[k] for k in person if k not in trailing}
    for key in trailing:
        entry[key] = person[key]
    assert list(order_official_fields(entry)) == EXPECTED_ORDER


def test_already_ordered_entry_is_unchanged():
    entry = _person()
    assert order_official_fields(entry) == entry
    assert list(order_official_fields(entry)) == list(entry)


def test_values_are_the_original_objects():
    entry = _person(phones=["(916) 808-5300"])
    ordered = order_official_fields(entry)
    assert ordered["phones"] is entry["phones"]
    assert ordered["office"] is entry["office"]


def test_absent_keys_are_not_invented():
    ordered = order_official_fields({"id": "a", "name": "Alice Adams"})
    assert list(ordered) == ["name", "id"]


def test_undeclared_keys_are_kept_at_the_end():
    entry = {"id": "a", "legacy_note": "keep me", "name": "Alice Adams"}
    assert list(order_official_fields(entry)) == ["name", "id", "legacy_note"]
