from pydantic import BaseModel

import database.changesets as changesets_db
import database.government_forms as government_forms_db
import services.jurisdiction_pull_request as jurisdiction_pr_service
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
from schemas.jurisdictions import GovernmentFormSummary, JurisdictionDetailsFields
from shared.schemas import GovernmentForm, JurisdictionLevel
from shared.utils.government_forms import (
    GOVERNMENT_FORM_DESCRIPTIONS,
    DerivedOrganization,
    government_form_name,
)
from shared.utils.layered_config import (
    allowed_government_forms,
    in_standard_order,
    derived_organizations,
    jurisdiction_config,
    resolve_government_form,
)
from shared.utils.id_utils import parse_jurisdiction_ocdid
from shared.utils.statuses import ActivityType


class ResolvedGovernment(BaseModel):
    government_form: GovernmentForm | None
    derived_organizations: list[DerivedOrganization]
    # What the config allows for it: the choices an LLM is offered when the government form is unknown.
    allowed_government_forms: list[GovernmentForm]


_NOTHING_RESOLVED = ResolvedGovernment(government_form=None, derived_organizations=[], allowed_government_forms=[])


async def resolved_government(jurisdiction_ocdid: str) -> ResolvedGovernment:
    """The jurisdiction's government form as of now (open-data's value, else what the config decides) and the
    organizations it implies. Nothing for a state, or an unknown or inactive jurisdiction."""
    jurisdiction = await government_forms_db.get_government_form_inputs(jurisdiction_ocdid)
    if jurisdiction is None:
        return _NOTHING_RESOLVED
    layer = _layer(jurisdiction)
    if layer is None:
        return _NOTHING_RESOLVED
    config = jurisdiction_config(await jurisdiction_configs_db.get_jurisdiction_configs(), *layer)
    government_form = resolve_government_form(config, jurisdiction.name, jurisdiction.government_form)
    return ResolvedGovernment(
        government_form=government_form,
        derived_organizations=derived_organizations(config, government_form),
        allowed_government_forms=allowed_government_forms(config, jurisdiction.name),
    )


async def government_form_summary(jurisdiction_ocdid: str) -> GovernmentFormSummary | None:
    """The resolved government form as the jurisdiction page shows it; None when no government form is known."""
    government_form = (await resolved_government(jurisdiction_ocdid)).government_form
    if government_form is None:
        return None
    return _summary(government_form)


async def government_form_options(jurisdiction_ocdid: str) -> list[GovernmentFormSummary]:
    """Every government form of the jurisdiction's level, which a maintainer may pick: not only the ones
    its state allows, since a jurisdiction can differ from its state (a charter county)."""
    parsed = parse_jurisdiction_ocdid(jurisdiction_ocdid)
    if parsed.level == JurisdictionLevel.STATE:
        return []
    configs = await jurisdiction_configs_db.get_jurisdiction_configs()
    level_forms = jurisdiction_config(configs, parsed.state, parsed.level).country_government_forms
    return [_summary(government_form) for government_form in in_standard_order(level_forms)]


def _summary(government_form: GovernmentForm) -> GovernmentFormSummary:
    return GovernmentFormSummary(
        value=government_form,
        name=government_form_name(government_form).capitalize(),
        description=GOVERNMENT_FORM_DESCRIPTIONS[government_form],
    )


async def organizations_with_role_labels(jurisdiction_ocdid: str) -> list[dict]:
    """Every organization in the jurisdiction with its posts and derived role labels."""
    organizations = await posts_db.list_by_organization(jurisdiction_ocdid)
    government = await resolved_government(jurisdiction_ocdid)
    return with_role_labels(organizations, government.derived_organizations)


async def ensure_government_form_organizations() -> int:
    """Build every active jurisdiction's derived organizations not built yet. Returns how many
    changed. The government form itself is never saved: open-data's value or the config files decide it.

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
        government_form = resolve_government_form(config, jurisdiction.name, jurisdiction.government_form)
        changes = organization_changes(
            derived_organizations(config, government_form), existing, DEFAULT_ORGANIZATION_NAME
        )
        if changes.has_no_changes:
            continue
        await _apply(jurisdiction, existing[0], changes)
        changed += 1
    return changed


def _layer(jurisdiction: GovernmentFormInputs) -> tuple[str, JurisdictionLevel] | None:
    """The (state, level) whose config files apply; None for a state, which has no government form."""
    parsed = parse_jurisdiction_ocdid(jurisdiction.jurisdiction_ocdid)
    if parsed.level == JurisdictionLevel.STATE:
        return None
    return parsed.state, parsed.level


async def _apply(
    jurisdiction: GovernmentFormInputs,
    default: ExistingOrganization,
    changes: OrganizationChanges,
) -> None:
    """Rename the default, create the rest, and log it: one transaction."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        if changes.rename_default_to is not None:
            await organizations_db.rename(cur, default.id, changes.rename_default_to)
        for organization in changes.organizations_to_create:
            await organizations_db.find_or_create(
                cur, jurisdiction.jurisdiction_ocdid, organization.name
            )
        fields = _organization_fields(default.name, changes)
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


async def government_form_choices(jurisdiction_ocdid: str) -> list[GovernmentForm]:
    """The government forms a run should ask the model to choose between, or none when it should not ask:
    the government form is known or decided by the config, a pull request is waiting, or a person closed
    one before (after that, a person sets it)."""
    government = await resolved_government(jurisdiction_ocdid)
    if government.government_form is not None or len(government.allowed_government_forms) < 2:
        return []
    if await jurisdiction_pr_service.has_open_pull_request(jurisdiction_ocdid):
        return []
    if await changesets_db.has_rejected_jurisdiction_pull_request(jurisdiction_ocdid):
        return []
    return government.allowed_government_forms


async def jurisdiction_details_fields(jurisdiction_ocdid: str) -> JurisdictionDetailsFields:
    waiting = await changesets_db.get_open_jurisdiction_pull_request(jurisdiction_ocdid)
    return JurisdictionDetailsFields(
        government_form=await government_form_summary(jurisdiction_ocdid),
        government_form_options=await government_form_options(jurisdiction_ocdid),
        open_pull_request_url=waiting.pull_request_url if waiting else None,
    )
