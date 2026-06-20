import logging

from environment import get_env_vars
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None


def _on_reconnect_failed(pool: AsyncConnectionPool) -> None:
    logger.error("Database connection pool failed to reconnect — pool may be exhausted")


async def get_pool() -> AsyncConnectionPool:
    env = get_env_vars()

    global _pool
    if _pool is None:
        db_url = env["CIVICPATCH_API_DB_URL"]
        if not db_url:
            raise RuntimeError("CIVICPATCH_API_DB_URL is not set")
        _pool = AsyncConnectionPool(
            db_url,
            open=False,
            min_size=int(env.get("DB_POOL_MIN_SIZE", 4)),
            max_size=int(env.get("DB_POOL_MAX_SIZE", 20)),
            reconnect_failed=_on_reconnect_failed,
        )
        try:
            # wait=True so a not-ready DB raises here instead of returning a dead pool that
            # silently wedges the caller; the process crashes and its restart policy retries.
            await _pool.open(wait=True, timeout=10)
        except Exception:
            _pool = None  # don't cache a half-open pool; let the next call rebuild it
            raise
        logger.info("Database pool opened")
    return _pool


async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


def to_iso(dt):
    if dt:
        return dt.isoformat()
    return None
