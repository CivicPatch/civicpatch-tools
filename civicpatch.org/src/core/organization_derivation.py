"""What a jurisdiction's derived organizations imply for its real ones: the changes to make,
and the role labels each serves with.

Pure: the derived organizations and the jurisdiction's organizations in.

The default organization is renamed to the first derived organization rather than replaced, so its
id, and with it every post id, membership id and human claim keyed to them, survives. No source
record moves. Whoever the form puts elsewhere (a Mayor under mayor_council) stays in the renamed
organization until the next reviewed scrape files them into their own and closes the old
membership.
"""

from pydantic import BaseModel

from shared.utils.government_forms import DerivedOrganization


class ExistingOrganization(BaseModel):
    id: str
    name: str
    meta_is_default: bool


class OrganizationChanges(BaseModel):
    # None when the default was renamed by hand, or the name is already taken.
    rename_default_to: str | None
    organizations_to_create: list[DerivedOrganization]

    @property
    def has_no_changes(self) -> bool:
        return self.rename_default_to is None and not self.organizations_to_create


def organization_changes(
    derived: list[DerivedOrganization],
    organizations: list[ExistingOrganization],
    original_default_name: str,
) -> OrganizationChanges:
    if not derived:
        return OrganizationChanges(rename_default_to=None, organizations_to_create=[])
    first, *others = derived
    existing_names = [organization.name for organization in organizations]
    defaults = [organization for organization in organizations if organization.meta_is_default]
    default_keeps_its_original_name = bool(defaults) and defaults[0].name == original_default_name
    rename = default_keeps_its_original_name and first.name not in existing_names
    return OrganizationChanges(
        rename_default_to=first.name if rename else None,
        organizations_to_create=[o for o in others if o.name not in existing_names],
    )


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
