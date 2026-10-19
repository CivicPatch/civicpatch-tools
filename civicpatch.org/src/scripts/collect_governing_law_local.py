"""Collect jurisdictions' governing law on the local pipelines server (dev only).

    mise run collect-governing-law -- <jurisdiction ocdid>...

Each starts at once: a collection is a few plain fetches, so there is no in-flight cap to keep.
"""

import asyncio
import sys

import services.governing_law_collector_runs as collector_runs_service
from database.database import close_pool
from database.users import SYSTEM_USER_ID

DISPATCH_MODE = "local"


async def main(jurisdiction_ocdids: list[str]) -> None:
    try:
        for jurisdiction_ocdid in jurisdiction_ocdids:
            claimed = await collector_runs_service.start_collection(jurisdiction_ocdid, SYSTEM_USER_ID, DISPATCH_MODE)
            print(f"{jurisdiction_ocdid}: run {claimed.pipeline_run_id}", flush=True)
    finally:
        await close_pool()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1:]))
