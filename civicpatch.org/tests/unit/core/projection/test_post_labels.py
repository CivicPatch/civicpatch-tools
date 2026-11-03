import pytest

from core.projection.facts import PostKey
from core.projection.post_labels import post_role_label
from shared.schemas import Role, RoleConfig
from shared.utils.taxonomy import build_taxonomy

_TAXONOMY = build_taxonomy(RoleConfig(roles=[Role(id="member", label="Member")]))
_COUNCIL = "org-council"
_POST = PostKey(organization_id=_COUNCIL, role_id="member", division_ocdid="ocd-division/country:us/state:zz")


@pytest.mark.unit
def test_a_post_is_named_by_what_its_organization_calls_the_role():
    labels = {_COUNCIL: {"member": "Select Board Member"}}

    assert post_role_label(_POST, labels, _TAXONOMY) == "Select Board Member"


@pytest.mark.unit
def test_else_the_roles_own_label_names_it():
    assert post_role_label(_POST, {}, _TAXONOMY) == "Member"


@pytest.mark.unit
def test_a_post_on_the_unmatched_placeholder_is_called_unmatched():
    post = _POST.model_copy(update={"role_id": "unmatched"})

    assert post_role_label(post, {}, _TAXONOMY) == "Unmatched"
