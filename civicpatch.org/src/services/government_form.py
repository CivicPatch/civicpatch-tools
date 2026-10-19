
import database.changesets as changesets_db
import database.government_forms as government_forms_db
import services.extras_organizations as extras_organizations_service
import services.governing_law as governing_law_service
import database.jurisdiction_configs as jurisdiction_configs_db
from core.organization_derivation import (
    ExistingOrganization,
    NOTHING_RESOLVED,
    OrganizationChanges,
    ResolvedGovernment,
    organization_changes,
    resolve_government,
    with_role_labels,
)
from core.post_deletion import with_holder_names
from database import organizations as organizations_db
from database import post_listings as post_listings_db
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
    government_form_name,
)
from shared.utils.layered_config import (
    MergedConfig,
    level_government_forms,
    derived_organizations,
    jurisdiction_config,
    resolve_government_form,
)
from shared.utils.id_utils import parse_jurisdiction_ocdid
from shared.utils.statuses import ActivityType
from shared.utils.taxonomy import build_taxonomy, role_labels_by_role_id


async def resolved_government(jurisdiction_ocdid: str) -> ResolvedGovernment:
    """The jurisdiction's government form as of now (the saved one, else what the config decides) and
    its candidates. Nothing for a state, or an unknown or inactive jurisdiction."""
    jurisdiction = await government_forms_db.get_government_form_inputs(jurisdiction_ocdid)
    layer = _layer(jurisdiction) if jurisdiction else None
    if jurisdiction is None or layer is None:
        return NOTHING_RESOLVED
    config = jurisdiction_config(await jurisdiction_configs_db.get_jurisdiction_configs(), *layer)
    return resolve_government(config, jurisdiction.name, jurisdiction.government_form)


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
    level_forms = level_government_forms(jurisdiction_config(configs, parsed.state, parsed.level))
    return [_summary(government_form) for government_form in level_forms]


def _summary(government_form: GovernmentForm) -> GovernmentFormSummary:
    return GovernmentFormSummary(
        value=government_form,
        name=government_form_name(government_form).capitalize(),
        description=GOVERNMENT_FORM_DESCRIPTIONS[government_form],
    )


async def organizations_with_role_labels(jurisdiction_ocdid: str) -> list[dict]:
    """Every organization in the jurisdiction with its posts and derived role labels."""
    organizations = await post_listings_db.list_by_organization(jurisdiction_ocdid)
    post_ids = [post["id"] for organization in organizations for post in organization["posts"]]
    holder_names = await post_listings_db.get_holder_names(post_ids)
    government = await resolved_government(jurisdiction_ocdid)
    return with_role_labels(with_holder_names(organizations, holder_names), government.candidate_organizations)


async def ensure_government_form_organizations() -> int:
    """Build every active jurisdiction's derived organizations not built yet. Returns how many
    changed. The saved government form, else the config files, decides which.

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
        layer = _layer(jurisdiction)
        if layer is None:
            continue
        existing = organizations.get(jurisdiction.jurisdiction_ocdid, [])
        if await _build_organizations(jurisdiction, config_by_layer[layer], existing):
            changed += 1
    return changed


async def build_government_form_organizations(jurisdiction_ocdid: str) -> None:
    """`ensure_government_form_organizations` for one jurisdiction, right after its form changes."""
    jurisdiction = await government_forms_db.get_government_form_inputs(jurisdiction_ocdid)
    layer = _layer(jurisdiction) if jurisdiction else None
    if jurisdiction is None or layer is None:
        return
    config = jurisdiction_config(await jurisdiction_configs_db.get_jurisdiction_configs(), *layer)
    existing = (await government_forms_db.list_organizations([jurisdiction_ocdid])).get(jurisdiction_ocdid, [])
    await _build_organizations(jurisdiction, config, existing)


async def _build_organizations(
    jurisdiction: GovernmentFormInputs, config: MergedConfig, existing: list[ExistingOrganization]
) -> bool:
    """Returns whether anything changed."""
    if not existing:
        return False
    government_form = resolve_government_form(config, jurisdiction.name, jurisdiction.government_form)
    derived = derived_organizations(config, government_form)
    changes = organization_changes(derived, existing, DEFAULT_ORGANIZATION_NAME)
    if changes.has_no_changes:
        return False
    taxonomy = build_taxonomy(config.roles)
    role_labels = {organization.name: role_labels_by_role_id(organization.role_labels, taxonomy) for organization in derived}
    await _apply(jurisdiction, existing[0], changes, role_labels)
    return True


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
    role_labels: dict[str, dict[str, str]],
) -> None:
    """Rename the default, create the rest, give each what the form calls its roles, and log
    it: one transaction. `role_labels` is per organization name."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        if changes.rename_default_to is not None:
            await organizations_db.rename(cur, default.id, changes.rename_default_to)
            await organizations_db.set_extras_role_labels(cur, default.id, role_labels[changes.rename_default_to])
        for organization in changes.organizations_to_create:
            organization_id = await organizations_db.find_or_create(
                cur, jurisdiction.jurisdiction_ocdid, organization.name
            )
            await organizations_db.set_extras_role_labels(cur, organization_id, role_labels[organization.name])
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
    """The government forms a run should ask the model to choose between, or none when the form is
    known or decided by the config."""
    government = await resolved_government(jurisdiction_ocdid)
    if government.government_form is not None or len(government.candidate_government_forms) < 2:
        return []
    return government.candidate_government_forms


class UnknownJurisdiction(Exception):
    pass


class GovernmentFormNotAtLevel(Exception):
    pass


async def set_government_form(jurisdiction_ocdid: str, government_form: GovernmentForm, user_id: str | None) -> None:
    """Saved over whatever was there. `user_id` is None for the service key."""
    jurisdiction = await _checked(jurisdiction_ocdid, government_form)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await government_forms_db.save_government_form(cur, jurisdiction_ocdid, government_form)
        await _record_government_form(cur, jurisdiction, government_form, user_id)
    await build_government_form_organizations(jurisdiction_ocdid)


async def _checked(jurisdiction_ocdid: str, government_form: GovernmentForm) -> GovernmentFormInputs:
    jurisdiction = await government_forms_db.get_government_form_inputs(jurisdiction_ocdid)
    if jurisdiction is None:
        raise UnknownJurisdiction(jurisdiction_ocdid)
    options = [option.value for option in await government_form_options(jurisdiction_ocdid)]
    if government_form not in options:
        raise GovernmentFormNotAtLevel(f"{government_form.value} is not a government form at this level")
    return jurisdiction


async def _record_government_form(
    cur, jurisdiction: GovernmentFormInputs, government_form: GovernmentForm, user_id: str | None
) -> None:
    await record_change(
        cur,
        ActivityType.EDIT_JURISDICTION,
        user_id,
        jurisdiction.jurisdiction_ocdid,
        Change(
            entity_type=EntityType.JURISDICTION,
            entity_id=jurisdiction.jurisdiction_ocdid,
            subject=jurisdiction.name,
            fields=[
                FieldChange(field="government_form", before=jurisdiction.government_form, after=government_form)
            ],
        ),
    )


async def jurisdiction_details_fields(jurisdiction_ocdid: str) -> JurisdictionDetailsFields:
    waiting = await changesets_db.get_open_jurisdiction_pull_request(jurisdiction_ocdid)
    saved = await government_forms_db.get_government_form_inputs(jurisdiction_ocdid)
    return JurisdictionDetailsFields(
        government_form=await government_form_summary(jurisdiction_ocdid),
        government_form_options=await government_form_options(jurisdiction_ocdid),
        open_pull_request_url=waiting.pull_request_url if waiting else None,
        # The column as saved; `government_form` is the resolved one, which config can decide.
        extras_government_form=saved.government_form if saved else None,
        extras_governing_law=await governing_law_service.get_governing_law(jurisdiction_ocdid),
        extras_organizations=await extras_organizations_service.get_extras_organizations(jurisdiction_ocdid),
    )
