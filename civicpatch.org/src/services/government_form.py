import database.government_forms as government_forms_db
from core.organization_derivation import (
    ExistingOrganization,
    OrganizationChanges,
    organization_changes_for_form,
)
from database import organizations as organizations_db
from database.activity import record_change
from database.database import get_pool
from database.government_forms import GovernmentFormInputs
from schemas.activity import Change, FieldChange
from schemas.claims import EntityType
from shared.schemas import GovernmentForm, JurisdictionLevel
from shared.utils.government_forms import (
    GovernmentFormsConfig,
    load_government_forms_config,
    resolve_government_form,
)
from shared.utils.id_utils import parse_jurisdiction_ocdid
from shared.utils.statuses import ActivityType


async def resolved_government_form(jurisdiction_ocdid: str) -> GovernmentForm | None:
    """The jurisdiction's form as of now: its government form, else what the config decides.

    None for a state, an unknown or inactive jurisdiction, or one the config leaves open.
    """
    jurisdiction = await government_forms_db.get_government_form_inputs(jurisdiction_ocdid)
    if jurisdiction is None:
        return None
    return _resolve(load_government_forms_config(), jurisdiction)


async def ensure_government_form_organizations() -> int:
    """Apply every active jurisdiction's form that is not applied yet. Returns how many changed.

    Run on every open-data sync, like `ensure_defaults_exist`. Two reads decide everything in
    memory; only a jurisdiction with something to change gets a write, so a run with nothing to
    do (nearly every run) writes nothing.
    """
    config = load_government_forms_config()
    jurisdictions = await government_forms_db.government_form_inputs_below_state()
    organizations = await government_forms_db.list_organizations(
        [jurisdiction.jurisdiction_ocdid for jurisdiction in jurisdictions]
    )
    changed = 0
    for jurisdiction in jurisdictions:
        existing = organizations.get(jurisdiction.jurisdiction_ocdid, [])
        form = _resolve(config, jurisdiction)
        if form is None or not existing:
            continue
        changes = organization_changes_for_form(form, existing)
        if changes.has_no_changes and jurisdiction.government_form is not None:
            continue
        await _apply(jurisdiction, form, existing[0], changes)
        changed += 1
    return changed


def _resolve(
    config: GovernmentFormsConfig, jurisdiction: GovernmentFormInputs
) -> GovernmentForm | None:
    parsed = parse_jurisdiction_ocdid(jurisdiction.jurisdiction_ocdid)
    if parsed.level == JurisdictionLevel.STATE:
        return None
    return resolve_government_form(
        config, parsed.state, parsed.level, jurisdiction.name, jurisdiction.government_form
    )


async def _apply(
    jurisdiction: GovernmentFormInputs,
    form: GovernmentForm,
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
        await government_forms_db.save_government_form_if_unset(
            cur, jurisdiction.jurisdiction_ocdid, form
        )
        await record_change(
            cur,
            ActivityType.EDIT_JURISDICTION,
            None,
            jurisdiction.jurisdiction_ocdid,
            _change(jurisdiction, form, default.name, changes),
        )


def _change(
    jurisdiction: GovernmentFormInputs,
    form: GovernmentForm,
    default_name: str,
    changes: OrganizationChanges,
) -> Change:
    fields = [FieldChange(field="government_form", before=None, after=form.value)]
    if changes.rename_default_to is not None:
        fields.append(
            FieldChange(field="organization_name", before=default_name, after=changes.rename_default_to)
        )
    for organization in changes.organizations_to_create:
        fields.append(FieldChange(field="organization_created", after=organization.name))
    return Change(
        entity_type=EntityType.JURISDICTION,
        entity_id=jurisdiction.jurisdiction_ocdid,
        subject=jurisdiction.name,
        fields=fields,
    )
