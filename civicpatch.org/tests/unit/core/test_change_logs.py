from datetime import datetime, timezone

import pytest

from core.change_logs import roster_change, summarize_change_log
from shared.utils.statuses import ChangeLogType


pytestmark = pytest.mark.unit


# ── Person events ───────────────────────────────────────────────────────


def test_add_person_uses_person_name():
    assert (
        summarize_change_log("add_person", {"subject": "Jane Doe", "fields": []})
        == "Added Jane Doe"
    )


def test_edit_person_pluralizes_fields_correctly():
    assert summarize_change_log("edit_person", {"subject": "J", "fields": [{}]}) == "Edited J (1 field)"
    assert summarize_change_log("edit_person", {"subject": "J", "fields": [{}, {}]}) == "Edited J (2 fields)"


def test_delete_person_omits_field_count_when_none():
    assert summarize_change_log("delete_person", {"subject": "J", "fields": []}) == "Deleted J"


def test_person_missing_name_falls_back():
    assert summarize_change_log("add_person", {}) == "Added record"


# ── Review events ───────────────────────────────────────────────────────


def test_review_events():
    assert summarize_change_log("publish_review", None) == "Published review"
    assert summarize_change_log("dismiss_review", None) == "Dismissed review"


# ── Role taxonomy ───────────────────────────────────────────────────────


def test_add_role_canonical():
    assert (
        summarize_change_log("add_role", {"role": "Mayor"})
        == "Added role 'Mayor'"
    )


def test_edit_role_summarizes_alias_deltas():
    payload = {"role": "Mayor", "aliases_added": ["hizzoner"], "aliases_removed": ["a", "b"]}
    assert summarize_change_log("edit_role", payload) == "Edited role 'Mayor' (+1 alias, -2 aliases)"


def test_edit_role_no_alias_changes():
    assert (
        summarize_change_log("edit_role", {"role": "Mayor"})
        == "Edited role 'Mayor'"
    )


def test_exclude_role():
    """Retired event type — existing change_log rows must still render."""
    assert (
        summarize_change_log("exclude_role", {"role": "Mayor"})
        == "Excluded role 'Mayor'"
    )


def test_include_role():
    """Retired event type — existing change_log rows must still render."""
    assert (
        summarize_change_log("include_role", {"role": "City Hall"})
        == "Included 'City Hall' as role"
    )


# ── Fallback / robustness ───────────────────────────────────────────────


def test_unknown_type_returns_type_string():
    assert summarize_change_log("brand_new_event", {"any": "thing"}) == "brand_new_event"


def test_none_changes_doesnt_crash():
    """A dismissal stores no payload at all — its reason is on `changesets.dismissed_reason`."""
    assert summarize_change_log("edit_jurisdiction", None) == "Edited record"
    assert summarize_change_log("dismiss_review", None) == "Dismissed review"


# ── Reorder events ──────────────────────────────────────────────────────


def test_reorder_to_top():
    payload = {"before": ["a", "b", "c"], "after": ["c", "a", "b"]}
    assert summarize_change_log("reorder_roles", payload) == "Reordered roles: 'c' moved to the top"


def test_reorder_below_neighbor():
    payload = {"before": ["a", "b", "c"], "after": ["a", "c", "b"]}
    assert summarize_change_log("reorder_roles", payload) == "Reordered roles: 'c' moved below 'a'"


def test_reorder_no_movers_falls_back():
    payload = {"before": ["a", "b"], "after": ["a", "b"]}
    assert summarize_change_log("reorder_roles", payload) == "Reordered roles"


def test_reorder_picks_furthest_mover():
    # 'mayor' jumps from the bottom to the top; the others only shift by one.
    payload = {
        "before": ["x", "y", "z", "mayor"],
        "after": ["mayor", "x", "y", "z"],
    }
    assert summarize_change_log("reorder_roles", payload) == "Reordered roles: 'mayor' moved to the top"


def test_reorder_lists_moved_roles_when_present():
    payload = {"before": ["a", "b", "c"], "after": ["c", "a", "b"], "moved": ["c", "a"]}
    assert summarize_change_log("reorder_roles", payload) == "Reordered roles: moved c, a"


def test_reorder_truncates_many_moved_roles():
    payload = {"moved": ["a", "b", "c", "d", "e"]}
    assert summarize_change_log("reorder_roles", payload) == "Reordered roles: moved a, b, c (+2 more)"


# ── Roster changes: the timeline entry's shape ──────────────────────────


def _change(type_, changes):
    return roster_change(type_, datetime(2026, 9, 2, tzinfo=timezone.utc), changes)


def test_a_membership_names_the_seat_it_assigns():
    """Without `detail` the only renderable thing left is the field name `post_id`, because a
    membership's subject is the person and the post's label would be dropped on the way out."""
    change = _change(
        ChangeLogType.ASSIGN_MEMBERSHIP,
        {"subject": "Ada Lovelace", "detail": "Council D3"},
    )

    assert change.name == "Ada Lovelace"
    assert change.detail == "Council D3"


def test_a_seat_with_no_label_falls_back_to_its_role():
    """`database.memberships.assign` resolves the fallback when it writes — the label if the
    seat has one, the role slug otherwise — so the reader gets a name either way."""
    change = _change(
        ChangeLogType.ASSIGN_MEMBERSHIP,
        {"subject": "Ada Lovelace", "detail": "council_member"},
    )

    assert change.detail == "council_member"


def test_only_memberships_carry_a_seat():
    """Every other type is fully described by its name plus the fields that moved, so a second
    subject would just be a duplicate to keep in sync."""
    change = _change(
        ChangeLogType.EDIT_PERSON,
        {"subject": "Ada Lovelace", "fields": [{"field": "email"}]},
    )

    assert change.detail is None


def test_an_assertion_carries_the_name_it_was_made_against():
    """Resolved when the assertion is written, not looked up on every read. The history used to
    query a name per row because the payload held only ids — and that could not answer at all
    once the entity had been deleted."""
    change = _change(
        ChangeLogType.ASSERT_FIELD,
        {
            "entity_type": "person",
            "entity_id": "abc",
            "subject": "Ada Lovelace",
            "fields": [{"field": "email", "after": "a@b.c"}],
        },
    )

    assert change.name == "Ada Lovelace"
    assert [f.field for f in change.fields] == ["email"]


def test_an_assertion_with_no_resolvable_name_falls_back_to_its_type():
    """`POST /assertions` writes the type when the lookup finds nothing — better a bare
    "person" than a uuid nobody can read."""
    change = _change(
        ChangeLogType.ASSERT_FIELD,
        {"entity_type": "person", "entity_id": "abc", "subject": "person"},
    )

    assert change.name == "person"
