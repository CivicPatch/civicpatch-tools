"""Load one open-data config file from stdin into this database, as the merge Action's sync does
for prod, without GitHub. Dev only: the path is the file's open-data path, the content is the
file itself.

    docker exec -i -w /app civicpatch-org python src/scripts/load_local_config.py data_source/vt/local/config.yml < ~/open-data/data_source/vt/local/config.yml

`mise run sync_dev_configs` restores dev to test-open-data's main afterwards.
"""

import asyncio
import sys

import database.jurisdiction_configs as jurisdiction_configs_db
from database.database import close_pool
from schemas.jurisdiction_configs import JurisdictionConfigVersion
from services.jurisdiction_config_sync import parse_jurisdiction_config

LOCAL_COMMIT_SHA = "local-working-tree"


async def main(path: str, raw: str) -> None:
    config = parse_jurisdiction_config(raw)
    version = JurisdictionConfigVersion(path=path, commit_sha=LOCAL_COMMIT_SHA, pull_request_number=None)
    try:
        await jurisdiction_configs_db.sync_jurisdiction_config(version, config)
        print(f"{path}: {len(config.roles)} roles, {len(config.government_forms)} forms", flush=True)
    finally:
        await close_pool()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], sys.stdin.read()))
