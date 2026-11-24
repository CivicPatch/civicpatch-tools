"""Which organizations a jurisdiction gets: the ones its law names once pipeline 2 has answered, else
what its merged config gives it. Created where missing, never renamed."""

from pydantic import BaseModel

from core.organization_derivation import resolve_government
from shared.schemas import GoverningLawOrganizations, GovernmentForm
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import MergedConfig, derived_organizations


class GovernmentFormInputs(BaseModel):
    """One active jurisdiction, with what resolving its government form reads."""

    jurisdiction_ocdid: str
    name: str
    government_form: GovernmentForm | None
    # The organizations its law names; None until pipeline 2 has answered with posts.
    law_organization_names: list[str] | None


class FormOrganizationRow(BaseModel):
    jurisdiction_ocdid: str
    name: str


def form_organization_rows(config: MergedConfig, jurisdictions: list[GovernmentFormInputs]) -> list[FormOrganizationRow]:
    rows = []
    for jurisdiction in jurisdictions:
        for organization in organizations_to_build(config, jurisdiction):
            rows.append(
                FormOrganizationRow(
                    jurisdiction_ocdid=jurisdiction.jurisdiction_ocdid,
                    name=organization.name,
                )
            )
    return rows


def law_organization_names(answer: GoverningLawOrganizations | None) -> list[str] | None:
    """The organizations an answer's posts name, in order; None for no answer, or one with no posts."""
    if answer is None or not answer.posts:
        return None
    names: list[str] = []
    for post in answer.posts:
        if post.organization_id not in names:
            names.append(post.organization_id)
    return names


def organizations_not_in_law(organizations: dict[str, str], law_names: list[str]) -> list[str]:
    """The ids, of `organizations` (id -> name), whose name the law does not give."""
    return [organization_id for organization_id, name in organizations.items() if name not in law_names]


def organizations_to_build(config: MergedConfig, jurisdiction: GovernmentFormInputs) -> list[DerivedOrganization]:
    """The law's organizations once there is an answer; until then the known form's. While the form is
    unknown, only the ones every allowed form lists: a Vermont town's two forms list the same ten; a city
    gets Council, and Office of the Mayor only once its form is saved as mayor_council."""
    if jurisdiction.law_organization_names is not None:
        return [DerivedOrganization(name=name, role_labels=[]) for name in jurisdiction.law_organization_names]
    government = resolve_government(config, jurisdiction.name, jurisdiction.government_form)
    if government.government_form is not None:
        return government.candidate_organizations
    shared = []
    for organization in government.candidate_organizations:
        listed_by_every_form = True
        for form in government.candidate_government_forms:
            names = [listed.name for listed in derived_organizations(config, form, jurisdiction.name)]
            if organization.name not in names:
                listed_by_every_form = False
        if listed_by_every_form:
            shared.append(organization)
    return shared
