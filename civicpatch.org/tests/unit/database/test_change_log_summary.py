import pytest

from database.change_log_summary import summarize_change_log


pytestmark = pytest.mark.unit


# ── Person events ───────────────────────────────────────────────────────


def test_add_person_uses_person_name():
    assert (
        summarize_change_log("add_person", {"person_name": "Jane Doe", "fields": []})
        == "Added Jane Doe"
    )


def test_edit_person_pluralizes_fields_correctly():
    assert summarize_change_log("edit_person", {"person_name": "J", "fields": [{}]}) == "Edited J (1 field)"
    assert summarize_change_log("edit_person", {"person_name": "J", "fields": [{}, {}]}) == "Edited J (2 fields)"


def test_delete_person_omits_field_count_when_none():
    assert summarize_change_log("delete_person", {"person_name": "J", "fields": []}) == "Deleted J"


def test_person_missing_name_falls_back():
    assert summarize_change_log("add_person", {}) == "Added person"


# ── Review events ───────────────────────────────────────────────────────


def test_review_events():
    assert summarize_change_log("merge_review", None) == "Merged review"
    assert summarize_change_log("close_review", None) == "Closed review"


# ── Role taxonomy ───────────────────────────────────────────────────────


def test_add_role_canonical():
    assert (
        summarize_change_log("add_role", {"role": "Mayor", "kind": "canonical"})
        == "Added role 'Mayor'"
    )


def test_add_role_exclusion_labels_correctly():
    assert (
        summarize_change_log("add_role", {"role": "City Hall", "kind": "exclusion"})
        == "Added exclusion 'City Hall'"
    )


def test_edit_role_summarizes_alias_deltas():
    payload = {"role": "Mayor", "kind": "canonical", "aliases_added": ["hizzoner"], "aliases_removed": ["a", "b"]}
    assert summarize_change_log("edit_role", payload) == "Edited role 'Mayor' (+1 alias, -2 aliases)"


def test_edit_role_no_alias_changes():
    assert (
        summarize_change_log("edit_role", {"role": "Mayor", "kind": "canonical"})
        == "Edited role 'Mayor'"
    )


def test_delete_role_includes_kind_label():
    assert (
        summarize_change_log("delete_role", {"role": "City Hall", "kind": "exclusion"})
        == "Removed exclusion 'City Hall'"
    )


def test_exclude_role():
    assert (
        summarize_change_log("exclude_role", {"role": "Mayor", "kind": "exclusion"})
        == "Excluded role 'Mayor'"
    )


def test_include_role():
    assert (
        summarize_change_log("include_role", {"role": "City Hall", "kind": "canonical"})
        == "Included exclusion 'City Hall' as role"
    )


# ── Fallback / robustness ───────────────────────────────────────────────


def test_unknown_type_returns_type_string():
    assert summarize_change_log("brand_new_event", {"any": "thing"}) == "brand_new_event"


def test_none_changes_doesnt_crash():
    assert summarize_change_log("edit_jurisdiction", None) == "Edited jurisdiction"
