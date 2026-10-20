"""A jurisdiction's governing law: cp.org's own column, written by the collector or a
maintainer, always replacing the last answer."""

import database.governing_law as governing_law_db
import database.jurisdiction_configs as jurisdiction_configs_db
from database.activity import record_change
from database.database import get_pool
from database.governing_law import GoverningLawRow
from schemas.activity import Change, FieldChange
from schemas.claims import EntityType
from pydantic import BaseModel
from shared.schemas import GoverningLaw, JurisdictionLevel
from shared.utils.id_utils import parse_jurisdiction_ocdid
from shared.utils.layered_config import GoverningLawConfig, jurisdiction_config
from shared.utils.statuses import ActivityType


class UnknownJurisdiction(Exception):
    pass


class CollectorConfig(BaseModel):
    """What a governing_law_collector run is told when it starts: what
    `/pipeline_runs/{id}/collector_config` answers for its kind."""

    name: str
    governing_law: GoverningLawConfig | None


async def set_governing_law(jurisdiction_ocdid: str, governing_law: GoverningLaw, user_id: str | None) -> None:
    """Saved over whatever was there: a yearly run replaces last year's answer. `user_id` is
    None for the collector's service key."""
    row = await governing_law_db.get_governing_law_row(jurisdiction_ocdid)
    if row is None:
        raise UnknownJurisdiction(jurisdiction_ocdid)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await governing_law_db.save_governing_law(cur, jurisdiction_ocdid, governing_law)
        await _record_governing_law(cur, row, governing_law, user_id)


async def get_governing_law(jurisdiction_ocdid: str) -> GoverningLaw | None:
    """None for an unknown jurisdiction, or one no collector run has written yet."""
    row = await governing_law_db.get_governing_law_row(jurisdiction_ocdid)
    return row.governing_law if row else None


async def _record_governing_law(
    cur, row: GoverningLawRow, governing_law: GoverningLaw, user_id: str | None
) -> None:
    before = row.governing_law.model_dump(mode="json") if row.governing_law else None
    await record_change(
        cur,
        ActivityType.EDIT_JURISDICTION,
        user_id,
        row.jurisdiction_ocdid,
        Change(
            entity_type=EntityType.JURISDICTION,
            entity_id=row.jurisdiction_ocdid,
            subject=row.name,
            fields=[FieldChange(field="governing_law", before=before, after=governing_law.model_dump(mode="json"))],
        ),
    )


async def collector_config(jurisdiction_ocdid: str) -> CollectorConfig:
    """The jurisdiction's name and its state's merged governing_law block for its level; no
    block for a state, or a state whose file has none yet."""
    row = await governing_law_db.get_governing_law_row(jurisdiction_ocdid)
    if row is None:
        raise UnknownJurisdiction(jurisdiction_ocdid)
    parsed = parse_jurisdiction_ocdid(jurisdiction_ocdid)
    if parsed.level == JurisdictionLevel.STATE:
        return CollectorConfig(name=row.name, governing_law=None)
    configs = await jurisdiction_configs_db.get_jurisdiction_configs()
    return CollectorConfig(name=row.name, governing_law=jurisdiction_config(configs, parsed.state, parsed.level).governing_law)
