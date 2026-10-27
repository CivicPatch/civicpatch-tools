"""Which organizations a merged config file gives each jurisdiction it governs. Applied when the
file merges: created where missing, labelled where unlabelled, never renamed or removed."""

from pydantic import BaseModel

from core.organization_derivation import resolve_government
from shared.schemas import GovernmentForm
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import MergedConfig, derived_organizations
from shared.utils.taxonomy import build_taxonomy, role_labels_by_role_id


class GovernmentFormInputs(BaseModel):
    """One active jurisdiction, with what resolving its government form reads."""

    jurisdiction_ocdid: str
    name: str
    government_form: GovernmentForm | None


class FormOrganizationRow(BaseModel):
    jurisdiction_ocdid: str
    name: str
    role_labels: dict[str, str]


def form_organization_rows(config: MergedConfig, jurisdictions: list[GovernmentFormInputs]) -> list[FormOrganizationRow]:
    taxonomy = build_taxonomy(config.roles)
    rows = []
    for jurisdiction in jurisdictions:
        for organization in organizations_to_build(config, jurisdiction):
            rows.append(
                FormOrganizationRow(
                    jurisdiction_ocdid=jurisdiction.jurisdiction_ocdid,
                    name=organization.name,
                    role_labels=role_labels_by_role_id(organization.role_labels, taxonomy),
                )
            )
    return rows


def organizations_to_build(config: MergedConfig, jurisdiction: GovernmentFormInputs) -> list[DerivedOrganization]:
    """The known form's organizations. While the form is unknown, only the ones every allowed form
    lists: a Vermont town's two forms list the same ten; a city gets Council, and Office of the
    Mayor only once its form is saved as mayor_council."""
    government = resolve_government(config, jurisdiction.name, jurisdiction.government_form)
    if government.government_form is not None:
        return government.candidate_organizations
    shared = []
    for organization in government.candidate_organizations:
        listed_by_every_form = True
        for form in government.candidate_government_forms:
            names = [listed.name for listed in derived_organizations(config, form)]
            if organization.name not in names:
                listed_by_every_form = False
        if listed_by_every_form:
            shared.append(organization)
    return shared
