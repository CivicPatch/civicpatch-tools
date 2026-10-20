"""Run a collector over jurisdictions on the local pipelines server (dev only).

    mise run collect -- <kind> <jurisdiction ocdid>...

Each starts at once: a collection is a handful of fetches or model calls, so there is no in-flight
cap to keep.
"""

import asyncio
import sys

import services.collector_runs as collector_runs_service
from database.database import close_pool
from database.users import SYSTEM_USER_ID
from shared.utils.statuses import PipelineRunKind

DISPATCH_MODE = "local"


async def main(kind: PipelineRunKind, jurisdiction_ocdids: list[str]) -> None:
    try:
        for jurisdiction_ocdid in jurisdiction_ocdids:
            claimed = await collector_runs_service.start_collection(kind, jurisdiction_ocdid, SYSTEM_USER_ID, DISPATCH_MODE)
            print(f"{jurisdiction_ocdid}: run {claimed.pipeline_run_id}", flush=True)
    finally:
        await close_pool()


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in collector_runs_service.CANDIDATES:
        sys.exit(__doc__)
    asyncio.run(main(PipelineRunKind(sys.argv[1]), sys.argv[2:]))
