from pydantic import BaseModel

import database.government_forms as government_forms_db
import database.jurisdiction_configs as jurisdiction_configs_db
from core.organization_derivation import (
    ExistingOrganization,
    OrganizationChanges,
    organization_changes,
    with_role_labels,
)
from database import organizations as organizations_db
from database import posts as posts_db
from database.organizations import DEFAULT_ORGANIZATION_NAME
from database.activity import record_change
from database.database import get_pool
from database.government_forms import GovernmentFormInputs
from schemas.activity import Change, FieldChange
from schemas.claims import EntityType
from schemas.jurisdictions import GovernmentFormSummary
from shared.schemas import GovernmentForm, JurisdictionLevel
from shared.utils.government_forms import (
    GOVERNMENT_FORM_DESCRIPTIONS,
    DerivedOrganization,
    government_form_name,
)
from shared.utils.layered_config import (
    derived_organizations,
    jurisdiction_config,
    resolve_government_form,
)
from shared.utils.id_utils import parse_jurisdiction_ocdid
from shared.utils.statuses import ActivityType


class ResolvedGovernment(BaseModel):
    government_form: GovernmentForm | None
    derived_organizations: list[DerivedOrganization]


_NOTHING_RESOLVED = ResolvedGovernment(government_form=None, derived_organizations=[])


async def resolved_government(jurisdiction_ocdid: str) -> ResolvedGovernment:
    """The jurisdiction's form as of now (its saved form, else what the config decides) and the
    organizations it implies. Nothing for a state, or an unknown or inactive jurisdiction."""
    jurisdiction = await government_forms_db.get_government_form_inputs(jurisdiction_ocdid)
    if jurisdiction is None:
        return _NOTHING_RESOLVED
    layer = _layer(jurisdiction)
    if layer is None:
        return _NOTHING_RESOLVED
    config = jurisdiction_config(await jurisdiction_configs_db.get_jurisdiction_configs(), *layer)
    form = resolve_government_form(config, jurisdiction.name, jurisdiction.government_form)
    return ResolvedGovernment(
        government_form=form, derived_organizations=derived_organizations(config, form)
    )


async def government_form_summary(jurisdiction_ocdid: str) -> GovernmentFormSummary | None:
    """The resolved form as the jurisdiction page shows it; None when no form is known."""
    form = (await resolved_government(jurisdiction_ocdid)).government_form
    if form is None:
        return None
    return GovernmentFormSummary(
        value=form,
        name=government_form_name(form).capitalize(),
        description=GOVERNMENT_FORM_DESCRIPTIONS[form],
    )


async def organizations_with_role_labels(jurisdiction_ocdid: str) -> list[dict]:
    """Every organization in the jurisdiction with its posts and derived role labels."""
    organizations = await posts_db.list_by_organization(jurisdiction_ocdid)
    government = await resolved_government(jurisdiction_ocdid)
    return with_role_labels(organizations, government.derived_organizations)


async def ensure_government_form_organizations() -> int:
    """Build every active jurisdiction's derived organizations not built yet, and save a
    rule-decided form. Returns how many changed.

    Run on every open-data sync, like `ensure_defaults_exist`. Two reads decide everything in
    memory; only a jurisdiction with something to change gets a write, so a run with nothing to
    do (nearly every run) writes nothing.
    """
    configs = await jurisdiction_configs_db.get_jurisdiction_configs()
    jurisdictions = await government_forms_db.government_form_inputs_below_state()
    layers = {layer for layer in map(_layer, jurisdictions) if layer is not None}
    config_by_layer = {layer: jurisdiction_config(configs, *layer) for layer in layers}
    organizations = await government_forms_db.list_organizations(
        [jurisdiction.jurisdiction_ocdid for jurisdiction in jurisdictions]
    )
    changed = 0
    for jurisdiction in jurisdictions:
        existing = organizations.get(jurisdiction.jurisdiction_ocdid, [])
        layer = _layer(jurisdiction)
        if not existing or layer is None:
            continue
        config = config_by_layer[layer]
        form = resolve_government_form(config, jurisdiction.name, jurisdiction.government_form)
        changes = organization_changes(
            derived_organizations(config, form), existing, DEFAULT_ORGANIZATION_NAME
        )
        form_is_saved = form == jurisdiction.government_form
        if changes.has_no_changes and form_is_saved:
            continue
        await _apply(jurisdiction, form, existing[0], changes)
        changed += 1
    return changed


def _layer(jurisdiction: GovernmentFormInputs) -> tuple[str, JurisdictionLevel] | None:
    """The (state, level) whose config files apply; None for a state, which has no form."""
    parsed = parse_jurisdiction_ocdid(jurisdiction.jurisdiction_ocdid)
    if parsed.level == JurisdictionLevel.STATE:
        return None
    return parsed.state, parsed.level


async def _apply(
    jurisdiction: GovernmentFormInputs,
    form: GovernmentForm | None,
    default: ExistingOrganization,
    changes: OrganizationChanges,
) -> None:
    """Rename the default, create the rest, save the form, and log it: one transaction."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        if changes.rename_default_to is not None:
            await organizations_db.rename(cur, default.id, changes.rename_default_to)
        for organization in changes.organizations_to_create:
            await organizations_db.find_or_create(
                cur, jurisdiction.jurisdiction_ocdid, organization.name
            )
        fields = _organization_fields(default.name, changes)
        if form is not None and await government_forms_db.save_government_form_if_unset(
            cur, jurisdiction.jurisdiction_ocdid, form
        ):
            fields.insert(0, FieldChange(field="government_form", before=None, after=form.value))
        await record_change(
            cur,
            ActivityType.EDIT_JURISDICTION,
            None,
            jurisdiction.jurisdiction_ocdid,
            Change(
                entity_type=EntityType.JURISDICTION,
                entity_id=jurisdiction.jurisdiction_ocdid,
                subject=jurisdiction.name,
                fields=fields,
            ),
        )


def _organization_fields(default_name: str, changes: OrganizationChanges) -> list[FieldChange]:
    fields = []
    if changes.rename_default_to is not None:
        fields.append(
            FieldChange(field="organization_name", before=default_name, after=changes.rename_default_to)
        )
    for organization in changes.organizations_to_create:
        fields.append(FieldChange(field="organization_created", after=organization.name))
    return fields
