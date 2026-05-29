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


def _upsert_term(cur, value: str, kind: str, is_unique: bool) -> str:
    """Insert or update a role_term at global scope; return its id."""
    cur.execute(
        """
        INSERT INTO role_terms (value, kind, jurisdiction_ocdid, display_name, is_unique, priority)
        VALUES (%s, %s, NULL, %s, %s, 0)
        ON CONFLICT ON CONSTRAINT role_terms_scope_uq
            DO UPDATE SET kind = EXCLUDED.kind, is_unique = EXCLUDED.is_unique
        RETURNING id::text
        """,
        (value, kind, value, is_unique),
    )
    row = cur.fetchone()
    assert row, "INSERT ... RETURNING id returned no row"
    return row[0]


def _upsert_alias(cur, term_id: str, alias: str):
    cur.execute(
        """
        INSERT INTO role_aliases (term_id, value, source)
        VALUES (%s, %s, 'curated')
        ON CONFLICT (term_id, value) WHERE disabled_at IS NULL DO NOTHING
        """,
        (term_id, alias),
    )


def import_taxonomy(path: str):
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    config = RoleConfig.model_validate(raw)

    db_url = os.environ["CIVICPATCH_API_DB_URL"]
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            for entry in config.roles:
                term_id = _upsert_term(cur, entry.role, entry.kind, entry.is_unique)
                for alias in entry.aliases:
                    _upsert_alias(cur, term_id, alias)

        conn.commit()

    total = len(config.roles)
    canonical = sum(1 for r in config.roles if r.kind == "canonical")
    exclusion = total - canonical
    print(f"Imported {total} role entries ({canonical} canonical, {exclusion} exclusions).")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    import_taxonomy(sys.argv[1])