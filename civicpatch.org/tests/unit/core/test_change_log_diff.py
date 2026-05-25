import pytest

from core.change_log_diff import diff_people
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
def test_office_is_diffed_by_component():
    result = diff_people([_person("1", office_name="Mayor")], [_person("1", office_name="Council Member")])
    fields = result[0].payload.fields
    assert [f.field for f in fields] == ["office.name"]
    assert (fields[0].before, fields[0].after) == ("Mayor", "Council Member")


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
