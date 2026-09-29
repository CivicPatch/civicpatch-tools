import pytest

from core.jurisdiction_config_sync import COUNTRY_ROLES_PATH, StoredRole, role_changes
from core.role_taxonomy import RoleOp
from shared.schemas import RoleStatus
from shared.utils.layered_config import ConfigRole

TENNESSEE = "data_source/tn/counties/config.yml"


def _stored(id_: str, label: str, path: str | None = COUNTRY_ROLES_PATH, **fields) -> StoredRole:
    return StoredRole(id=id_, label=label, config_path=path, **fields)


@pytest.mark.unit
def test_a_new_role_is_added_with_its_aliases_and_file_position():
    role = ConfigRole(id="mayor", label="Mayor", aliases=["town mayor"])

    changes = role_changes(COUNTRY_ROLES_PATH, [role], [])

    [upsert] = changes.upserts
    assert (upsert.op, upsert.priority, upsert.aliases_added) == (RoleOp.ADD, 0, {"town mayor"})


@pytest.mark.unit
def test_an_unchanged_role_needs_nothing():
    stored = _stored("mayor", "Mayor", priority=0, aliases=["town mayor"])

    changes = role_changes(COUNTRY_ROLES_PATH, [ConfigRole(id="mayor", label="Mayor", aliases=["town mayor"])], [stored])

    assert changes.upserts == []
    assert changes.deactivations == []


@pytest.mark.unit
def test_a_new_label_on_a_known_id_is_a_rename():
    stored = _stored("select-board-member", "Selectman", priority=0)

    changes = role_changes(COUNTRY_ROLES_PATH, [ConfigRole(id="select-board-member", label="Select Board Member")], [stored])

    assert [upsert.op for upsert in changes.upserts] == [RoleOp.EDIT]


@pytest.mark.unit
def test_an_alias_change_alone_is_not_an_edit():
    stored = _stored("mayor", "Mayor", priority=0, aliases=["town mayor"])

    changes = role_changes(COUNTRY_ROLES_PATH, [ConfigRole(id="mayor", label="Mayor", aliases=["city mayor"])], [stored])

    [upsert] = changes.upserts
    assert (upsert.op, upsert.aliases_added, upsert.aliases_removed) == (
        RoleOp.NO_CHANGE,
        {"city mayor"},
        {"town mayor"},
    )


@pytest.mark.unit
def test_a_moved_role_gets_its_new_priority():
    stored = [_stored("mayor", "Mayor", priority=0), _stored("council-member", "Council Member", priority=1)]
    file_roles = [ConfigRole(id="council-member", label="Council Member"), ConfigRole(id="mayor", label="Mayor")]

    changes = role_changes(COUNTRY_ROLES_PATH, file_roles, stored)

    assert [(upsert.role.id, upsert.priority) for upsert in changes.upserts] == [("council-member", 0), ("mayor", 1)]


@pytest.mark.unit
def test_an_inactive_role_listed_again_is_reactivated():
    stored = _stored("chair", "Chair", priority=0, status=RoleStatus.INACTIVE)

    changes = role_changes(COUNTRY_ROLES_PATH, [ConfigRole(id="chair", label="Chair")], [stored])

    assert [upsert.op for upsert in changes.upserts] == [RoleOp.EDIT]


@pytest.mark.unit
def test_a_role_the_file_dropped_is_deactivated():
    stored = [_stored("mayor", "Mayor", priority=0), _stored("select-board-chair", "Select Board Chair", priority=1)]

    changes = role_changes(COUNTRY_ROLES_PATH, [ConfigRole(id="mayor", label="Mayor")], stored)

    assert [role.id for role in changes.deactivations] == ["select-board-chair"]


@pytest.mark.unit
def test_a_role_another_file_defines_is_left_alone():
    stored = [_stored("county-mayor", "County Mayor", path=TENNESSEE), _stored("unmatched", "Unmatched", path=None)]

    assert role_changes(COUNTRY_ROLES_PATH, [], stored).deactivations == []


@pytest.mark.unit
def test_state_roles_are_unranked_and_move_to_their_file():
    stored = _stored("county-mayor", "County Mayor", priority=12)

    changes = role_changes(TENNESSEE, [ConfigRole(id="county-mayor", label="County Mayor")], [stored])

    [upsert] = changes.upserts
    assert (upsert.op, upsert.priority) == (RoleOp.EDIT, None)
