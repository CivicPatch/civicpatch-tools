import pytest

from core.role_taxonomy import (
    RoleOp,
    build_event_payload,
    change_log_type,
    classify_role_op,
    diff_aliases,
    name_conflict_error,
    reorder_validation_error,
    slug_conflict_error,
    slugify_label,
)
from schemas.roles import RoleInput
from shared.schemas import Role


# Pure helpers — unit-tested directly, no DB.
# The SQL read/write functions that call them live in
# tests/integration/database/test_roles.py.


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


# ── classify_role_op ────────────────────────────────────────────────────


def _entry(role: str, *, is_unique: bool = False, status: str = "active") -> RoleInput:
    return RoleInput.model_validate({
        "label": role, "status": status, "is_unique": is_unique, "aliases": [],
    })


def _stored(role: str, *, is_unique: bool = False, status: str = "active",
            aliases: list[str] | None = None) -> Role:
    """A role as read back from the DB. Distinct from RoleInput on purpose: the
    stored side carries the id and priority the submitted side has no say over."""
    return Role.model_validate({
        "id": slugify_label(role), "label": role, "status": status,
        "is_unique": is_unique, "aliases": aliases or [],
    })


@pytest.mark.unit
def test_classify_new_role_is_add():
    assert classify_role_op(_entry("Mayor"), None) is RoleOp.ADD


@pytest.mark.unit
def test_classify_unchanged_role_is_no_change():
    assert classify_role_op(_entry("Mayor"), _stored("Mayor")) is RoleOp.NO_CHANGE


@pytest.mark.unit
def test_classify_is_unique_change_is_edit():
    op = classify_role_op(
        _entry("Mayor", is_unique=True), _stored("Mayor", is_unique=False)
    )
    assert op is RoleOp.EDIT


@pytest.mark.unit
def test_classify_same_is_unique_is_no_change():
    op = classify_role_op(
        _entry("Mayor", is_unique=True), _stored("Mayor", is_unique=True)
    )
    assert op is RoleOp.NO_CHANGE


@pytest.mark.unit
def test_classify_status_change_is_edit():
    op = classify_role_op(
        _entry("City Manager", status="active"),
        _stored("City Manager", status="excluded"),
    )
    assert op is RoleOp.EDIT


@pytest.mark.unit
def test_classify_ignores_priority():
    """reorder_roles owns ordering and RoleInput has no priority field, so a
    stored role's priority can never make an entry look edited."""
    stored = Role.model_validate({
        "id": "mayor", "label": "Mayor", "status": "active",
        "is_unique": True, "priority": 10, "aliases": [],
    })
    assert classify_role_op(_entry("Mayor", is_unique=True), stored) is RoleOp.NO_CHANGE


@pytest.mark.unit
def test_classify_ignores_label_because_rename_is_not_expressible():
    """Lookup matches on exact label, so a classified pair always shares one.
    Renaming is #2476, not this path — the old label comparison here could never
    fire."""
    assert classify_role_op(_entry("Mayor"), _stored("Mayor")) is RoleOp.NO_CHANGE


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


# ── name_conflict_error ─────────────────────────────────────────────────


def _aliased(label: str, aliases: list[str]) -> RoleInput:
    return RoleInput.model_validate({"label": label, "aliases": aliases})


@pytest.mark.unit
def test_names_are_clean_when_every_string_is_distinct():
    entries = [_aliased("Mayor", ["hizzoner"]), _aliased("Clerk", ["recorder"])]
    assert name_conflict_error(entries, {}) is None


@pytest.mark.unit
def test_alias_claiming_a_stored_roles_label_conflicts():
    """The gap no index closes — role_aliases_label_lower_uq spans one table."""
    error = name_conflict_error([_aliased("Clerk", ["Mayor"])], {"Mayor": _stored("Mayor")})
    assert error is not None
    assert "claimed by both" in error


@pytest.mark.unit
def test_alias_claiming_a_label_in_the_same_payload_conflicts():
    entries = [_aliased("Mayor", []), _aliased("Clerk", ["Mayor"])]
    assert name_conflict_error(entries, {}) is not None


@pytest.mark.unit
def test_name_matching_is_case_insensitive():
    error = name_conflict_error([_aliased("Clerk", ["MAYOR"])], {"Mayor": _stored("Mayor")})
    assert error is not None


@pytest.mark.unit
def test_same_alias_on_two_roles_conflicts():
    error = name_conflict_error([_aliased("Clerk", ["chief"])], {"Mayor": _stored("Mayor", aliases=["Chief"])})
    assert error is not None


@pytest.mark.unit
def test_case_variant_aliases_within_one_role_conflict():
    """diff_aliases treats the list as a set, so both survive as two INSERTs and
    collide on lower(label)."""
    error = name_conflict_error([_aliased("Mayor", ["boss", "Boss"])], {})
    assert error is not None
    assert "more than once" in error


@pytest.mark.unit
def test_a_role_may_restate_its_own_label_as_an_alias():
    """Redundant, not ambiguous — it resolves to itself, and seeded rows do it
    (`Select Board Member`). Rejecting it would make those rows unsaveable."""
    assert name_conflict_error([_aliased("Mayor", ["Mayor"])], {}) is None
    assert name_conflict_error([_aliased("Mayor", ["mayor"])], {}) is None


@pytest.mark.unit
def test_a_submitted_entry_replaces_its_stored_aliases():
    """Dropping an alias must not read as a conflict with the row it replaces."""
    entries = [_aliased("Mayor", ["hizzoner"])]
    assert name_conflict_error(entries, {"Mayor": _stored("Mayor", aliases=["hizzoner", "the mayor"])}) is None


# ── slug_conflict_error ─────────────────────────────────────────────────


@pytest.mark.unit
def test_distinct_slugs_are_clean():
    entries = [_aliased("Mayor", []), _aliased("Clerk", [])]
    assert slug_conflict_error(entries, {}) is None


@pytest.mark.unit
def test_labels_reducing_to_one_slug_conflict():
    """unique (lower(label)) lets these through; the primary key does not."""
    error = slug_conflict_error(
        [_aliased("Council/Member", [])], {"Council Member": _stored("Council Member")}
    )
    assert error is not None
    assert "council-member" in error


@pytest.mark.unit
def test_two_new_labels_reducing_to_one_slug_conflict():
    entries = [_aliased("Council Member", []), _aliased("Council-Member", [])]
    assert slug_conflict_error(entries, {}) is not None


@pytest.mark.unit
def test_a_stored_role_keeps_its_own_slug():
    """An entry matching a stored label is an update — it mints no new id, so it
    cannot collide with itself."""
    entries = [_aliased("Council Member", [])]
    assert slug_conflict_error(entries, {"Council Member": _stored("Council Member")}) is None


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
