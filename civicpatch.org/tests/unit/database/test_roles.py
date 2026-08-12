import pytest

from database.roles import (
    TermOp,
    _state_ocdid_from_ocdid,
    build_event_payload,
    classify_term_op,
    diff_aliases,
    reorder_validation_error,
)
from shared.schemas import RoleConfig, Role


# Pure helpers — unit-tested directly, no DB.
# The SQL read/write functions live in tests/integration/database/test_roles.py.


# ── _state_ocdid_from_ocdid ─────────────────────────────────────────────


@pytest.mark.unit
def test_state_ocdid_from_place_appends_jurisdiction_type():
    """State-scope key must include the jurisdiction_type suffix so it round-
    trips through parse_jurisdiction_ocdid as a valid state-level OCDID."""
    ocdid = "ocd-jurisdiction/country:us/state:tx/place:combes/government"
    assert _state_ocdid_from_ocdid(ocdid) == "ocd-jurisdiction/country:us/state:tx/government"


@pytest.mark.unit
def test_state_ocdid_from_state_only_returns_itself():
    ocdid = "ocd-jurisdiction/country:us/state:tx/government"
    assert _state_ocdid_from_ocdid(ocdid) == "ocd-jurisdiction/country:us/state:tx/government"


@pytest.mark.unit
def test_state_ocdid_from_bare_country_is_none():
    assert _state_ocdid_from_ocdid("ocd-jurisdiction/country:us") is None


# ── classify_term_op ────────────────────────────────────────────────────


def _entry(role: str) -> Role:
    return Role.model_validate({
        "label": role, "is_unique": False, "aliases": [],
    })


@pytest.mark.unit
def test_classify_new_term_is_add():
    op, log = classify_term_op(_entry("Mayor"), None)
    assert op == TermOp.ADD
    assert log == "add_role"


@pytest.mark.unit
def test_classify_unchanged_term_is_no_change():
    op, log = classify_term_op(_entry("Mayor"), _entry("Mayor"))
    assert op == TermOp.NO_CHANGE
    assert log is None


# ── classify_term_op: is_unique edits ───────────────────────────────────


def _unique_entry(role: str, *, is_unique: bool) -> Role:
    return Role.model_validate({
        "label": role, "is_unique": is_unique, "aliases": [],
    })


@pytest.mark.unit
def test_classify_is_unique_change_is_edit():
    op, log = classify_term_op(
        _unique_entry("Mayor", is_unique=True),
        _unique_entry("Mayor", is_unique=False),
    )
    assert op == TermOp.EDIT
    assert log == "edit_role"


@pytest.mark.unit
def test_classify_same_is_unique_is_no_change():
    op, log = classify_term_op(
        _unique_entry("Mayor", is_unique=True),
        _unique_entry("Mayor", is_unique=True),
    )
    assert op == TermOp.NO_CHANGE
    assert log is None


@pytest.mark.unit
def test_classify_label_change_is_edit():
    entry = Role.model_validate({"label": "City Commissioner", "is_unique": False, "aliases": []})
    existing = Role.model_validate({"label": "Council Member", "is_unique": False, "aliases": []})
    op, log = classify_term_op(entry, existing)
    assert op == TermOp.EDIT
    assert log == "edit_role"


@pytest.mark.unit
def test_classify_status_change_is_edit():
    entry = Role.model_validate({"label": "City Manager", "status": "active", "is_unique": False, "aliases": []})
    existing = Role.model_validate({"label": "City Manager", "status": "rejected", "is_unique": False, "aliases": []})
    op, log = classify_term_op(entry, existing)
    assert op == TermOp.EDIT
    assert log == "edit_role"


@pytest.mark.unit
def test_classify_priority_change_is_edit():
    entry = Role.model_validate({"label": "Mayor", "is_unique": True, "priority": 5, "aliases": []})
    existing = Role.model_validate({"label": "Mayor", "is_unique": True, "priority": 10, "aliases": []})
    op, log = classify_term_op(entry, existing)
    assert op == TermOp.EDIT
    assert log == "edit_role"


# ── build_event_payload ─────────────────────────────────────────────────


@pytest.mark.unit
def test_payload_is_just_the_role_when_aliases_unchanged():
    payload = build_event_payload(_entry("Mayor"), set(), set())
    assert payload == {"role": "Mayor"}


@pytest.mark.unit
def test_payload_folds_alias_deltas_sorted():
    payload = build_event_payload(_entry("Mayor"), {"hizzoner", "the mayor"}, {"old"})
    assert payload["aliases_added"] == ["hizzoner", "the mayor"]
    assert payload["aliases_removed"] == ["old"]


@pytest.mark.unit
def test_payload_omits_empty_alias_deltas():
    payload = build_event_payload(_entry("Mayor"), set(), set())
    assert "aliases_added" not in payload
    assert "aliases_removed" not in payload


# ── diff_aliases ────────────────────────────────────────────────────────


@pytest.mark.unit
def test_diff_aliases_no_change():
    assert diff_aliases(["a", "b"], ["a", "b"]) == (set(), set())


@pytest.mark.unit
def test_diff_aliases_pure_add():
    to_disable, to_add = diff_aliases([], ["a", "b"])
    assert to_disable == set()
    assert to_add == {"a", "b"}


@pytest.mark.unit
def test_diff_aliases_pure_remove():
    to_disable, to_add = diff_aliases(["a", "b"], [])
    assert to_disable == {"a", "b"}
    assert to_add == set()


@pytest.mark.unit
def test_diff_aliases_mixed():
    to_disable, to_add = diff_aliases(["a", "b"], ["b", "c"])
    assert to_disable == {"a"}
    assert to_add == {"c"}


@pytest.mark.unit
def test_diff_aliases_dedups_incoming():
    """Incoming list with duplicates is treated as a set."""
    _, to_add = diff_aliases([], ["a", "a", "b"])
    assert to_add == {"a", "b"}


# ── reorder_validation_error ────────────────────────────────────────────


@pytest.mark.unit
def test_reorder_valid_permutation_is_none():
    assert reorder_validation_error(["a", "b", "c"], ["c", "a", "b"]) is None


@pytest.mark.unit
def test_reorder_empty_is_none():
    assert reorder_validation_error([], []) is None


@pytest.mark.unit
def test_reorder_missing_role_errors():
    err = reorder_validation_error(["a", "b"], ["a"])
    assert err is not None
    assert "b" in err


@pytest.mark.unit
def test_reorder_unexpected_role_errors():
    err = reorder_validation_error(["a"], ["a", "b"])
    assert err is not None
    assert "b" in err


@pytest.mark.unit
def test_reorder_duplicate_errors():
    err = reorder_validation_error(["a", "b"], ["a", "a"])
    assert err is not None
    assert "duplicate" in err.lower()
