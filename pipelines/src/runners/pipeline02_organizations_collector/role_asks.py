"""Which roles EXTRACT asks about: one fixed question per role, since an open "list every role"
answer varied run to run (56% agreement on Vermont's 88). Pure: config in, asks out."""

from typing import List

from pydantic import BaseModel
from shared.schemas import GovernmentForm, Role, SelectionMethod
from shared.utils.layered_config import MergedConfig, allowed_government_forms, derived_organizations
from shared.utils.taxonomy import build_taxonomy, lookup_key


class RoleAsk(BaseModel):
    organization_name: str
    role_id: str
    # What the question calls the role: the organization's label for it.
    role_label: str
    # Every way the law may write it, the label first, then the role's own label and aliases:
    # what VERIFY looks for in a quote.
    names: List[str]


def role_asks(config: MergedConfig, name: str, government_form: GovernmentForm | None) -> List[RoleAsk]:
    """Every role the jurisdiction's form gives its organizations; with no form set yet, those of
    every form its name allows. Then every role a body may choose from its members, under the
    first organization. A role asked once, in the first organization naming it."""
    forms = [government_form] if government_form is not None else allowed_government_forms(config, name)
    organizations = [organization for form in forms for organization in derived_organizations(config, form)]
    taxonomy = build_taxonomy(config.roles)
    roles_by_id = {role.id: role for role in config.roles.roles}
    asks: List[RoleAsk] = []
    for organization in organizations:
        for role_label in organization.role_labels:
            canonical = taxonomy.role_aliases.get(lookup_key(role_label))
            role_id = taxonomy.role_ids.get(canonical) if canonical else None
            if role_id is not None:
                asks = _with_ask(asks, organization.name, roles_by_id[role_id], role_label)
    for role in _presiding_candidates(config) if organizations else []:
        asks = _with_ask(asks, organizations[0].name, role, role.label)
    return asks


# The config marks no role as presiding; a default of chosen-by-members is what such offices share.
def _presiding_candidates(config: MergedConfig) -> List[Role]:
    return [role for role in config.roles.roles if role.selection_method == SelectionMethod.ELECTED_BY_MEMBERS]


def _with_ask(asks: List[RoleAsk], organization_name: str, role: Role, role_label: str) -> List[RoleAsk]:
    if any(ask.role_id == role.id for ask in asks):
        return asks
    names = list(dict.fromkeys([role_label, role.label, *role.aliases]))
    return [*asks, RoleAsk(organization_name=organization_name, role_id=role.id, role_label=role_label, names=names)]
