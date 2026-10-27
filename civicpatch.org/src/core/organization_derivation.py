"""What a jurisdiction's derived organizations imply for its real ones: the changes to make,
and the role labels each serves with.

Pure: the derived organizations and the jurisdiction's organizations in.

The default organization, `{lsad} Officers`, is born with the jurisdiction (`ensure_defaults_exist`).
The form's other organizations come from a state's data migration, never from code.
"""

from pydantic import BaseModel

from shared.schemas import GovernmentForm
from shared.utils.government_forms import DerivedOrganization, name_suffix
from shared.utils.layered_config import (
    MergedConfig,
    allowed_government_forms,
    derived_organizations,
    resolve_government_form,
)


LEGAL_STATUS_WORDS = ("city", "town", "township", "county", "village", "borough", "plantation")
DEFAULT_ORGANIZATION_SUFFIX = "Officers"


def default_organization_name(jurisdiction_name: str) -> str:
    """"Essex town" -> "Town Officers"; names that end in no legal status word -> "Officers"."""
    suffix = name_suffix(jurisdiction_name)
    if suffix not in LEGAL_STATUS_WORDS:
        return DEFAULT_ORGANIZATION_SUFFIX
    return f"{suffix.capitalize()} {DEFAULT_ORGANIZATION_SUFFIX}"


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
        candidate_organizations=merged_by_name([derived_organizations(config, form) for form in candidates]),
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


def with_role_labels(
    organizations: list[dict], derived: list[DerivedOrganization]
) -> list[dict]:
    """Each organization with the role labels of the derived organization of the same name, or
    none. The pick list before any post exists, and where research files a role."""
    labels_by_name = {organization.name: organization.role_labels for organization in derived}
    return [
        {**organization, "role_labels": labels_by_name.get(organization["name"], [])}
        for organization in organizations
    ]
