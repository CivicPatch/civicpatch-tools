from functools import lru_cache
from pathlib import Path

import yaml

from schemas.elections import Election

_ELECTIONS_PATH = Path("src/elections.yaml")


@lru_cache(maxsize=None)
def _load_elections() -> list[Election]:
    with open(_ELECTIONS_PATH) as f:
        raw = yaml.safe_load(f) or []
    return [Election.model_validate(e) for e in raw]


async def get_upcoming_elections() -> list[Election]:
    return _load_elections()
