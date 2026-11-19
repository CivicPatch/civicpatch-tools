"""What a jurisdiction's derived organizations imply for its real ones: the changes to make,
and the role labels each serves with.

Pure: the derived organizations and the jurisdiction's organizations in.

The default organization, `{lsad} Officers`, is born with the jurisdiction (`ensure_defaults_exist`).
The form's other organizations come from a state's data migration, never from code.
"""

from collections.abc import Mapping

from pydantic import BaseModel

from shared.schemas import GoverningLawOrganizations, GovernmentForm
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import (
    MergedConfig,
    allowed_government_forms,
    derived_organizations,
    resolve_government_form,
)
from shared.utils.taxonomy import Taxonomy, lookup_key


class ResolvedGovernment(BaseModel):
    government_form: GovernmentForm | None
    # The known form alone, or while it is unknown every form the config lists for the name.
    candidate_government_forms: list[GovernmentForm]
    # Those forms' organizations, merged by name.
    candidate_organizations: list[DerivedOrganization]


NOTHING_RESOLVED = ResolvedGovernment(
    government_form=None, candidate_government_forms=[], candidate_organizations=[]
)


def resolve_government(
    config: MergedConfig, name: str, saved_form: GovernmentForm | None
) -> ResolvedGovernment:
    government_form = resolve_government_form(config, name, saved_form)
    candidates = [government_form] if government_form else allowed_government_forms(config, name)
    return ResolvedGovernment(
        government_form=government_form,
        candidate_government_forms=candidates,
        candidate_organizations=merged_by_name([derived_organizations(config, form, name) for form in candidates]),
    )


def merged_by_name(per_form: list[list[DerivedOrganization]]) -> list[DerivedOrganization]:
    """Every form's organizations as one list: same-named ones become one, their role labels
    unioned in order. For a jurisdiction whose form is unknown, where any allowed form may hold."""
    labels_by_name: dict[str, list[str]] = {}
    for organizations in per_form:
        for organization in organizations:
            labels = labels_by_name.setdefault(organization.name, [])
            labels.extend(label for label in organization.role_labels if label not in labels)
    return [DerivedOrganization(name=name, role_labels=labels) for name, labels in labels_by_name.items()]


# A claim on an organization: a role it holds in this place that the law and config do not say,
# or one they say that it does not hold (an office created by ordinance, one voted away).
ROLES_FIELD = "roles"


class OrganizationRole(BaseModel):
    role: str
    label: str


class ClaimedRoles(BaseModel):
    accepted: list[OrganizationRole] = []
    rejected: list[OrganizationRole] = []


NO_CLAIMED_ROLES = ClaimedRoles()


def role_labels_by_organization(
    answer: GoverningLawOrganizations | None,
    derived: list[DerivedOrganization],
    taxonomy: Taxonomy,
    claimed: Mapping[str, ClaimedRoles],
) -> dict[str, dict[str, str]]:
    """Organization name -> role id -> what it calls the role: the place's own law for each
    organization it quotes a post for, else the config's form, then what people claimed."""
    labels_by_name = {organization.name: _role_ids_to_labels(organization.role_labels, taxonomy) for organization in derived}
    from_law: dict[str, dict[str, str]] = {}
    for post in answer.posts if answer else []:
        from_law.setdefault(post.organization_id, {})[post.role] = post.label
    merged = {**labels_by_name, **from_law}
    names = list(dict.fromkeys([*merged, *claimed]))
    return {name: _with_claimed(merged.get(name, {}), claimed.get(name, NO_CLAIMED_ROLES)) for name in names}


def _with_claimed(labels: dict[str, str], claimed: ClaimedRoles) -> dict[str, str]:
    accepted = {**labels, **{claim.role: claim.label for claim in claimed.accepted}}
    rejected = {claim.role for claim in claimed.rejected}
    return {role: label for role, label in accepted.items() if role not in rejected}


def _role_ids_to_labels(role_labels: list[str], taxonomy: Taxonomy) -> dict[str, str]:
    # Keeps a role's own label beside its aliases: readers need every role the form gives.
    labels: dict[str, str] = {}
    for text in role_labels:
        canonical = taxonomy.role_aliases.get(lookup_key(text))
        if canonical is not None:
            labels.setdefault(taxonomy.role_ids[canonical], text)
    return labels


def with_role_labels(
    organizations: list[dict], derived: list[DerivedOrganization], labels_by_name: dict[str, dict[str, str]]
) -> list[dict]:
    """Each organization with the labels its place calls its roles, then the config form's for it, or
    none. The pick list before any post exists, and where research files a role."""
    config_labels = {organization.name: organization.role_labels for organization in derived}
    return [
        {
            **organization,
            "role_labels": list(
                dict.fromkeys([*labels_by_name.get(organization["name"], {}).values(), *config_labels.get(organization["name"], [])])
            ),
        }
        for organization in organizations
    ]
