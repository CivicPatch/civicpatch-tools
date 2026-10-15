import pytest
from shared.schemas import RoleStatus
from shared.utils.layered_config import ConfigFile, ConfigRole
from shared.utils.yaml_utils import yaml_load

from core.role_config_edits import (
    RoleConfigEditRefused,
    edited_config_text,
    with_role_added,
    with_role_edited,
    with_role_order,
    without_role,
)
from schemas.roles import RoleInput

pytestmark = pytest.mark.unit

_CONFIG = """roles:
- id: mayor
  label: Mayor
  is_unique: true
  aliases: []
- id: council-member
  label: Council Member
  is_unique: false
  aliases:
  - councilmember
  - councilman
- id: trustee
  label: Trustee
  is_unique: false
  aliases: []
"""


def _roles() -> list[ConfigRole]:
    return ConfigFile.model_validate(yaml_load(_CONFIG)).roles


def _ids(roles: list[ConfigRole]) -> list[str]:
    return [role.id for role in roles]


def test_an_added_role_joins_the_end_with_its_slug_as_id():
    added = with_role_added(
        _roles(), RoleInput(label="Village President", is_unique=True, aliases=["president of the village"])
    )

    assert added[-1] == ConfigRole(
        id="village-president", label="Village President", is_unique=True, aliases=["president of the village"]
    )
    assert _ids(added) == ["mayor", "council-member", "trustee", "village-president"]


def test_adding_a_label_already_listed_is_refused():
    with pytest.raises(RoleConfigEditRefused):
        with_role_added(_roles(), RoleInput(label="council member"))


def test_an_edit_replaces_the_aliases():
    edited = with_role_edited(_roles(), "council-member", RoleInput(label="Council Member", aliases=["alder"]))

    assert edited[1].aliases == ["alder"]


def test_a_renamed_role_keeps_its_id():
    edited = with_role_edited(_roles(), "council-member", RoleInput(label="Councilmember"))

    assert _ids(edited) == ["mayor", "council-member", "trustee"]
    assert edited[1].label == "Councilmember"


def test_editing_an_unlisted_role_changes_nothing():
    assert with_role_edited(_roles(), "unmatched", RoleInput(label="Unmatched")) == _roles()


def test_a_role_that_is_not_active_is_refused():
    with pytest.raises(RoleConfigEditRefused):
        with_role_edited(_roles(), "trustee", RoleInput(label="Trustee", status=RoleStatus.INACTIVE))


def test_an_alias_naming_another_roles_label_is_refused():
    with pytest.raises(RoleConfigEditRefused):
        with_role_edited(_roles(), "trustee", RoleInput(label="Trustee", aliases=["Mayor"]))


def test_removing_by_id():
    assert _ids(without_role(_roles(), "mayor")) == ["council-member", "trustee"]


def test_removing_an_unlisted_role_changes_nothing():
    assert without_role(_roles(), "unmatched") == _roles()


def test_reordering_follows_the_given_order_and_ignores_ids_the_file_does_not_list():
    reordered = with_role_order(_roles(), ["trustee", "unmatched", "mayor", "council-member"])

    assert _ids(reordered) == ["trustee", "mayor", "council-member"]


def test_an_order_leaving_out_a_listed_role_is_refused():
    with pytest.raises(RoleConfigEditRefused):
        with_role_order(_roles(), ["mayor", "trustee"])


def test_the_input_roles_are_left_unchanged():
    roles = _roles()

    with_role_added(roles, RoleInput(label="Clerk"))
    with_role_edited(roles, "trustee", RoleInput(label="Village Trustee"))
    without_role(roles, "mayor")

    assert roles == _roles()


def test_an_edit_changes_only_its_own_lines_in_the_file():
    text = edited_config_text(_CONFIG, lambda roles: with_role_edited(roles, "mayor", RoleInput(label="Mayor")))

    assert text == _CONFIG.replace("label: Mayor\n  is_unique: true\n", "label: Mayor\n  is_unique: false\n")


def test_an_unchanged_list_writes_the_file_back_as_it_was():
    assert edited_config_text(_CONFIG, lambda roles: roles) == _CONFIG
