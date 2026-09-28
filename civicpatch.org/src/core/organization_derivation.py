"""The organization changes a government form implies for one jurisdiction.

Pure: the form and the jurisdiction's organizations in; what to rename and what to create out.

The default organization is renamed to the form's first organization rather than replaced, so its
id, and with it every post id, membership id and human claim keyed to them, survives. No source
record moves. Whoever the form puts elsewhere (a Mayor under mayor_council) stays in the renamed
organization until the next reviewed scrape files them into their own and closes the old
membership.
"""

from pydantic import BaseModel

from shared.schemas import GovernmentForm
from shared.utils.government_forms import DerivedOrganization, organizations_for


class ExistingOrganization(BaseModel):
    id: str
    name: str
    meta_is_default: bool


class OrganizationChanges(BaseModel):
    # None when the name is already taken, by the default itself or by a hand-made organization.
    rename_default_to: str | None
    organizations_to_create: list[DerivedOrganization]

    @property
    def has_no_changes(self) -> bool:
        return self.rename_default_to is None and not self.organizations_to_create


def organization_changes_for_form(
    form: GovernmentForm, organizations: list[ExistingOrganization]
) -> OrganizationChanges:
    first, *others = organizations_for(form)
    existing_names = [organization.name for organization in organizations]
    return OrganizationChanges(
        rename_default_to=None if first.name in existing_names else first.name,
        organizations_to_create=[o for o in others if o.name not in existing_names],
    )
