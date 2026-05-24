import json

from database.database import get_pool
from schemas.change_logs import PersonChangePayload
from shared.utils.statuses import ChangeLogType


async def create_change_log(
    change_type: ChangeLogType,
    user_id: str | None,
    jurisdiction_ocdid: str | None = None,
    request_id: str | None = None,
    changes: PersonChangePayload | None = None,
) -> None:
    payload = json.dumps(changes.model_dump(by_alias=True)) if changes else None
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO change_logs (type, jurisdiction_ocdid, request_id, changes, user_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (change_type, jurisdiction_ocdid, request_id, payload, user_id),
        )
