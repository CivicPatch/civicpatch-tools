import pytest

from core.people_diff import diff_people
from shared.utils.statuses import ChangeLogType


def _person(person_id, name="Jane Doe", office_name="Mayor", **extra):
    return {
        "id": person_id,
        "name": name,
        "office": {"name": office_name, "division_ocdid": "ocd-division/country:us"},
        "emails": [],
        "phones": [],
        "urls": [],
        "start_date": None,
        "end_date": None,
        **extra,
    }


# ── no-op ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_identical_lists_produce_no_changes():
    people = [_person("1")]
    assert diff_people(people, people) == []


# ── edit_person ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_changed_field_emits_edit_person():
    result = diff_people([_person("1", name="Jane Doe")], [_person("1", name="Jane Smith")])
    assert len(result) == 1
    assert result[0].type == ChangeLogType.EDIT_PERSON
    assert [(f.field, f.before, f.after) for f in result[0].payload.fields] == [("name", "Jane Doe", "Jane Smith")]


@pytest.mark.unit
def test_office_is_not_diffed_since_the_editor_stopped_writing_it():
    """The reviewer picks a `post_id` now, so `office` is the same on both sides of every edit
    and diffing it only ever reported nothing."""
    result = diff_people([_person("1", office_name="Mayor")], [_person("1", office_name="Council Member")])
    assert result == []


@pytest.mark.unit
@pytest.mark.parametrize("field, before, after", [
    ("image", "https://x.gov/old.png", "https://x.gov/new.png"),
    ("source_urls", ["https://x.gov/a"], ["https://x.gov/b"]),
    ("other_names", [], ["J. Doe"]),
])
def test_fields_a_reviewer_can_edit_are_diffed(field, before, after):
    """All three were left out — `image` and `source_urls` as noise, `other_names` never added
    — from before the reviewer could edit any of them. An edit nobody records is one the feed
    says did not happen."""
    result = diff_people([_person("1", **{field: before})], [_person("1", **{field: after})])
    assert [(f.field, f.before, f.after) for f in result[0].payload.fields] == [
        (field, before, after)
    ]


# ── add_person ──────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_new_id_emits_add_person_with_null_from():
    result = diff_people([], [_person("1", name="New Person")])
    assert result[0].type == ChangeLogType.ADD_PERSON
    assert result[0].payload.person_name == "New Person"
    name_field = next(f for f in result[0].payload.fields if f.field == "name")
    assert (name_field.before, name_field.after) == (None, "New Person")


# ── delete_person ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_missing_id_emits_delete_person_with_null_to():
    result = diff_people([_person("1", name="Gone")], [])
    assert result[0].type == ChangeLogType.DELETE_PERSON
    name_field = next(f for f in result[0].payload.fields if f.field == "name")
    assert (name_field.before, name_field.after) == ("Gone", None)


# ── mixed ───────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_mixed_add_edit_delete():
    before = [_person("1", name="Edit Me"), _person("2", name="Delete Me")]
    after = [_person("1", name="Edited"), _person("3", name="Added")]
    result = diff_people(before, after)
    assert {c.type for c in result} == {
        ChangeLogType.EDIT_PERSON,
        ChangeLogType.ADD_PERSON,
        ChangeLogType.DELETE_PERSON,
    }


# ── re-link (id changes, content identical) ───────────────────────────────────

@pytest.mark.unit
def test_relink_to_existing_id_with_same_content_is_no_change():
    # Matching a scraped person to an existing record changes only their id;
    # identical content must not surface as an add + delete.
    before = [_person("scraped-tmp-id", name="Matt Moore")]
    after = [_person("existing-matthew-id", name="Matt Moore")]
    assert diff_people(before, after) == []


@pytest.mark.unit
def test_distinct_people_still_add_and_delete():
    # Different content must NOT be cancelled as a re-link.
    result = diff_people([_person("a", name="Alice")], [_person("b", name="Bob")])
    assert {c.type for c in result} == {ChangeLogType.ADD_PERSON, ChangeLogType.DELETE_PERSON}
