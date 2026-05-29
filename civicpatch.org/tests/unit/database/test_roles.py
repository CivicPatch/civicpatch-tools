import pytest

from database.roles import (
    TermKind,
    TermOp,
    _state_ocdid_from_ocdid,
    build_event_payload,
    classify_term_op,
    diff_aliases,
)
from schemas.jurisdictions import RoleEntryData


# Pure helpers — unit-tested directly, no DB.
# The SQL read/write functions live in tests/integration/database/test_roles.py.


# ── _state_ocdid_from_ocdid ─────────────────────────────────────────────


@pytest.mark.unit
def test_state_ocdid_from_place():
    ocdid = "ocd-jurisdiction/country:us/state:tx/place:combes"
    assert _state_ocdid_from_ocdid(ocdid) == "ocd-jurisdiction/country:us/state:tx"


@pytest.mark.unit
def test_state_ocdid_from_state_returns_itself():
    ocdid = "ocd-jurisdiction/country:us/state:tx"
    assert _state_ocdid_from_ocdid(ocdid) == "ocd-jurisdiction/country:us/state:tx"


@pytest.mark.unit
def test_state_ocdid_from_bare_country_is_none():
    assert _state_ocdid_from_ocdid("ocd-jurisdiction/country:us") is None


# ── classify_term_op ────────────────────────────────────────────────────


def _entry(role: str, *, kind: str = "canonical") -> RoleEntryData:
    return RoleEntryData.model_validate({
        "role": role, "is_unique": False, "aliases": [], "kind": kind,
    })


@pytest.mark.unit
def test_classify_new_canonical_is_add():
    op, log = classify_term_op(_entry("Mayor"), existing_kind=None)
    assert op == TermOp.ADD
    assert log == "add_role"


@pytest.mark.unit
def test_classify_new_exclusion_is_add():
    """Adding an exclusion is the same op as adding a canonical — kind goes in payload."""
    op, log = classify_term_op(_entry("City Hall", kind="exclusion"), existing_kind=None)
    assert op == TermOp.ADD
    assert log == "add_role"


@pytest.mark.unit
def test_classify_canonical_to_exclusion_is_flip():
    op, log = classify_term_op(_entry("Mayor", kind="exclusion"), existing_kind=TermKind.CANONICAL)
    assert op == TermOp.FLIP_KIND
    assert log == "exclude_role"


@pytest.mark.unit
def test_classify_exclusion_to_canonical_is_flip():
    op, log = classify_term_op(_entry("Mayor"), existing_kind=TermKind.EXCLUSION)
    assert op == TermOp.FLIP_KIND
    assert log == "include_role"


@pytest.mark.unit
def test_classify_unchanged_canonical_is_no_change():
    op, log = classify_term_op(_entry("Mayor"), existing_kind=TermKind.CANONICAL)
    assert op == TermOp.NO_CHANGE
    assert log is None


@pytest.mark.unit
def test_classify_unchanged_exclusion_is_no_change():
    op, log = classify_term_op(_entry("City Hall", kind="exclusion"), existing_kind=TermKind.EXCLUSION)
    assert op == TermOp.NO_CHANGE
    assert log is None


# ── classify_term_op: is_unique edits ───────────────────────────────────


def _unique_entry(role: str, *, is_unique: bool, kind: str = "canonical") -> RoleEntryData:
    return RoleEntryData.model_validate({
        "role": role, "is_unique": is_unique, "aliases": [], "kind": kind,
    })


@pytest.mark.unit
def test_classify_is_unique_change_is_edit():
    op, log = classify_term_op(
        _unique_entry("Mayor", is_unique=True),
        existing_kind=TermKind.CANONICAL,
        existing_is_unique=False,
    )
    assert op == TermOp.EDIT
    assert log == "edit_role"


@pytest.mark.unit
def test_classify_same_is_unique_is_no_change():
    op, log = classify_term_op(
        _unique_entry("Mayor", is_unique=True),
        existing_kind=TermKind.CANONICAL,
        existing_is_unique=True,
    )
    assert op == TermOp.NO_CHANGE
    assert log is None


# ── build_event_payload ─────────────────────────────────────────────────


@pytest.mark.unit
def test_payload_includes_kind():
    payload = build_event_payload(_entry("Mayor"), set(), set())
    assert payload == {"role": "Mayor", "kind": "canonical"}


@pytest.mark.unit
def test_payload_includes_kind_for_exclusion():
    payload = build_event_payload(_entry("City Hall", kind="exclusion"), set(), set())
    assert payload == {"role": "City Hall", "kind": "exclusion"}


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
    assert diff_aliases({"a", "b"}, ["a", "b"]) == (set(), set())


@pytest.mark.unit
def test_diff_aliases_pure_add():
    to_disable, to_add = diff_aliases(set(), ["a", "b"])
    assert to_disable == set()
    assert to_add == {"a", "b"}


@pytest.mark.unit
def test_diff_aliases_pure_remove():
    to_disable, to_add = diff_aliases({"a", "b"}, [])
    assert to_disable == {"a", "b"}
    assert to_add == set()


@pytest.mark.unit
def test_diff_aliases_mixed():
    to_disable, to_add = diff_aliases({"a", "b"}, ["b", "c"])
    assert to_disable == {"a"}
    assert to_add == {"c"}


@pytest.mark.unit
def test_diff_aliases_dedups_incoming():
    """Incoming list with duplicates is treated as a set."""
    _, to_add = diff_aliases(set(), ["a", "a", "b"])
    assert to_add == {"a", "b"}
