#!/usr/bin/env python3
"""
Idempotent import of role taxonomy from a RoleConfig YAML into the DB tables.

Reads a YAML file matching the RoleConfig shape (used by open-data config.yml)
and upserts into roles, role_aliases, and role_exclusions. Safe to re-run.

Dev usage:
    CIVICPATCH_API_DB_URL=postgres://civicpatch:development_password@127.0.0.1:8003/development_db \
      uv run scripts/import_role_taxonomy.py seed/role_taxonomy.yml

Prod usage (via docker compose exec, requires psycopg + pyyaml in the container):
    docker compose exec -T civicpatch-org \
      python3 -c "
        import subprocess, sys
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'psycopg[binary]', 'pyyaml'], check=True)
      "
    docker compose exec -T civicpatch-org \
      python3 - < scripts/import_role_taxonomy.py seed/role_taxonomy.yml

    # Or add the script to the image and just:
    docker compose exec civicpatch-org python3 scripts/import_role_taxonomy.py seed/role_taxonomy.yml
"""
import os
import sys

import psycopg
import yaml
from shared.utils.config_utils import RoleConfig


def _upsert_role(cur, value: str, is_unique: bool):
    cur.execute(
        """
        INSERT INTO roles (value, display_name, jurisdiction_ocdid, is_unique, priority)
        VALUES (%s, %s, NULL, %s, 0)
        ON CONFLICT (value, jurisdiction_ocdid)
            WHERE disabled_at IS NULL
            DO UPDATE SET priority = 0
        """,
        (value, value, is_unique),
    )


def _resolve_role_id(cur, value: str) -> str:
    cur.execute(
        "SELECT id::text FROM roles WHERE value = %s AND jurisdiction_ocdid IS NULL AND disabled_at IS NULL",
        (value,),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Role '{value}' not found after upsert (bug?)")
    return row[0]


def _upsert_role_alias(cur, role_id: str, alias: str):
    cur.execute(
        """
        INSERT INTO role_aliases (role_id, value, source)
        VALUES (%s, %s, 'curated')
        ON CONFLICT (role_id, value)
            WHERE disabled_at IS NULL
            DO NOTHING
        """,
        (role_id, alias),
    )


def _upsert_exclusion(cur, value: str):
    cur.execute(
        """
        INSERT INTO role_exclusions (value, jurisdiction_ocdid, source)
        VALUES (%s, NULL, 'curated')
        ON CONFLICT (value, jurisdiction_ocdid)
            WHERE disabled_at IS NULL
            DO NOTHING
        """,
        (value,),
    )


def import_taxonomy(path: str):
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    config = RoleConfig.model_validate(raw)

    db_url = os.environ["CIVICPATCH_API_DB_URL"]
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            for entry in config.roles:
                if not entry.include:
                    _upsert_exclusion(cur, entry.role)
                    for alias in entry.aliases:
                        _upsert_exclusion(cur, alias)
                    continue

                _upsert_role(cur, entry.role, entry.is_unique)
                role_id = _resolve_role_id(cur, entry.role)
                for alias in entry.aliases:
                    _upsert_role_alias(cur, role_id, alias)

        conn.commit()

    total = len(config.roles)
    incl = sum(1 for r in config.roles if r.include)
    excl = total - incl
    print(f"Imported {total} role entries ({incl} roles, {excl} exclusions).")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    import_taxonomy(sys.argv[1])