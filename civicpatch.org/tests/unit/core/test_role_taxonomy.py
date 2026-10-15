import pytest

from core.role_taxonomy import (
    RoleOp,
    build_event_payload,
    change_log_type,
    diff_aliases,
    slugify_label,
)


# Pure helpers — unit-tested directly, no DB.


# ── slugify_label ───────────────────────────────────────────────────────


@pytest.mark.unit
def test_slugify_lowercases_and_hyphenates():
    assert slugify_label("Council Member") == "council-member"


@pytest.mark.unit
def test_slugify_collapses_punctuation_runs():
    assert slugify_label("Mayor Pro-Tem (Acting)") == "mayor-pro-tem-acting"


@pytest.mark.unit
def test_slugify_trims_leading_and_trailing_separators():
    """The migration's backfill wraps its regexp_replace in trim(both '-'),
    so a label with edge punctuation must not produce a dangling hyphen."""
    assert slugify_label("  Clerk & Treasurer  ") == "clerk-treasurer"


# ── change_log_type ─────────────────────────────────────────────────────


@pytest.mark.unit
def test_add_logs_as_add_role():
    assert change_log_type(RoleOp.ADD) == "add_role"


@pytest.mark.unit
def test_edit_and_alias_only_change_both_log_as_edit_role():
    """NO_CHANGE reaches change_log_type only when the row stood but its aliases
    moved, which is still an edit of the role."""
    assert change_log_type(RoleOp.EDIT) == "edit_role"
    assert change_log_type(RoleOp.NO_CHANGE) == "edit_role"


# ── build_event_payload ─────────────────────────────────────────────────


@pytest.mark.unit
def test_payload_is_just_the_role_when_aliases_unchanged():
    payload = build_event_payload("Mayor", set(), set())
    assert payload == {"role": "Mayor"}


@pytest.mark.unit
def test_payload_folds_alias_deltas_sorted():
    payload = build_event_payload("Mayor", {"hizzoner", "the mayor"}, {"old"})
    assert payload["aliases_added"] == ["hizzoner", "the mayor"]
    assert payload["aliases_removed"] == ["old"]


@pytest.mark.unit
def test_payload_omits_empty_alias_deltas():
    payload = build_event_payload("Mayor", set(), set())
    assert "aliases_added" not in payload
    assert "aliases_removed" not in payload


# ── diff_aliases ────────────────────────────────────────────────────────


@pytest.mark.unit
def test_diff_aliases_no_change():
    assert diff_aliases(["a", "b"], ["a", "b"]) == (set(), set())


@pytest.mark.unit
def test_diff_aliases_pure_add():
    to_add, to_disable = diff_aliases([], ["a", "b"])
    assert to_disable == set()
    assert to_add == {"a", "b"}


@pytest.mark.unit
def test_diff_aliases_pure_remove():
    to_add, to_disable = diff_aliases(["a", "b"], [])
    assert to_disable == {"a", "b"}
    assert to_add == set()


@pytest.mark.unit
def test_diff_aliases_mixed():
    to_add, to_disable = diff_aliases(["a", "b"], ["b", "c"])
    assert to_disable == {"a"}
    assert to_add == {"c"}


@pytest.mark.unit
def test_diff_aliases_dedups_incoming():
    """Incoming list with duplicates is treated as a set."""
    to_add, _ = diff_aliases([], ["a", "a", "b"])
    assert to_add == {"a", "b"}
