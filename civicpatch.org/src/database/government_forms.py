import database.jurisdiction_configs as jurisdiction_configs_db
from core.organization_build import GovernmentFormInputs
from core.organization_derivation import NOTHING_RESOLVED, ResolvedGovernment, resolve_government
from database.database import get_pool
from shared.schemas import GovernmentForm, JurisdictionLevel
from shared.utils.id_utils import parse_jurisdiction_ocdid
from shared.utils.layered_config import jurisdiction_config

# cp.org's own column, set by a person or a scrape; the open-data sync never writes it.
_INPUTS_SELECT = "SELECT jurisdiction_ocdid, data->>'name', extras_government_form FROM jurisdictions"


def _inputs(row) -> GovernmentFormInputs:
    return GovernmentFormInputs(jurisdiction_ocdid=row[0], name=row[1] or "", government_form=row[2])


async def get_government_form_inputs(jurisdiction_ocdid: str) -> GovernmentFormInputs | None:
    """None for an unknown or inactive jurisdiction."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            _INPUTS_SELECT + " WHERE jurisdiction_ocdid = %s AND status = 'active'",
            (jurisdiction_ocdid,),
        )
        row = await cur.fetchone()
    return _inputs(row) if row else None


async def get_resolved_government(jurisdiction_ocdid: str) -> ResolvedGovernment:
    """The jurisdiction's government form as of now (the saved one, else what the config decides) and
    its candidates. Nothing for a state, or an unknown or inactive jurisdiction."""
    jurisdiction = await get_government_form_inputs(jurisdiction_ocdid)
    layer = config_layer(jurisdiction) if jurisdiction else None
    if jurisdiction is None or layer is None:
        return NOTHING_RESOLVED
    config = jurisdiction_config(await jurisdiction_configs_db.get_jurisdiction_configs(), *layer)
    return resolve_government(config, jurisdiction.name, jurisdiction.government_form)


def config_layer(jurisdiction: GovernmentFormInputs) -> tuple[str, JurisdictionLevel] | None:
    """The (state, level) whose config files apply; None for a state, which has no government form."""
    parsed = parse_jurisdiction_ocdid(jurisdiction.jurisdiction_ocdid)
    if parsed.level == JurisdictionLevel.STATE:
        return None
    return parsed.state, parsed.level


async def list_government_form_inputs(cur, state: str, level: str) -> list[GovernmentFormInputs]:
    """Every active jurisdiction of one state and level: what a merged config file governs."""
    await cur.execute(
        _INPUTS_SELECT + " WHERE state = %s AND level = %s AND status = 'active' ORDER BY jurisdiction_ocdid",
        (state, level),
    )
    return [_inputs(row) for row in await cur.fetchall()]


async def save_government_form(cur, jurisdiction_ocdid: str, government_form: GovernmentForm) -> None:
    await cur.execute(
        "UPDATE jurisdictions SET extras_government_form = %s WHERE jurisdiction_ocdid = %s",
        (government_form, jurisdiction_ocdid),
    )
