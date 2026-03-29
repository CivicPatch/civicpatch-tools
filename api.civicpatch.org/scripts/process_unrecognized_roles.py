#!/usr/bin/env python3
"""
Scheduled script: for each pending unrecognized role, ask Gemini whether it maps
to a canonical role in roles.yml or is genuinely new, then open a single PR to
add any novel roles as stubs.

This script is ready but the GitHub Actions workflow is commented out.
Run manually: uv run python api.civicpatch.org/scripts/process_unrecognized_roles.py
"""
import asyncio
import base64
import json
import logging
import os
import time
from typing import List, Optional

import httpx
import jwt
import yaml
from google import genai
from google.genai import types
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROLES_YML_PATH = "shared/src/shared/config/roles.yml"
GEMINI_MODEL = "gemini-2.5-flash"


# ── Response schema for Gemini ──────────────────────────────────────────────

class RoleSuggestion(BaseModel):
    role: str
    canonical_match: Optional[str]  # None if no match found


class UnrecognizedRoleSuggestionResponseSchema(BaseModel):
    suggestions: List[RoleSuggestion]


# ── DB helpers ───────────────────────────────────────────────────────────────

async def get_pending_roles(pool: AsyncConnectionPool) -> list[dict]:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT DISTINCT role FROM unrecognized_roles WHERE status = 'pending'"
        )
        rows = await cur.fetchall()
    return [{"role": r[0]} for r in rows]


async def update_roles_status(
    pool: AsyncConnectionPool, roles: list[str], status: str, pr_url: Optional[str] = None
) -> None:
    async with pool.connection() as conn:
        if pr_url:
            await conn.execute(
                "UPDATE unrecognized_roles SET status = %s, pr_url = %s WHERE role = ANY(%s) AND status = 'pending'",
                (status, pr_url, roles),
            )
        else:
            await conn.execute(
                "UPDATE unrecognized_roles SET status = %s WHERE role = ANY(%s) AND status = 'pending'",
                (status, roles),
            )


# ── Gemini helper ────────────────────────────────────────────────────────────

def build_prompt(unknown_roles: list[str], canonical_roles: list[str]) -> str:
    roles_list = "\n".join(f"- {r}" for r in canonical_roles)
    unknown_list = "\n".join(f"- {r}" for r in unknown_roles)
    return f"""You are classifying municipal government role strings.

CANONICAL ROLES (from roles.yml):
{roles_list}

UNKNOWN ROLES to classify:
{unknown_list}

For each unknown role, determine whether it matches one of the canonical roles
(including common aliases, plurals, or minor variations). If it does, return the
canonical role name. If it is genuinely a new, distinct role type not covered by
any canonical role, return null for canonical_match.

Return one suggestion per unknown role, in the same order.
"""


def call_gemini(api_key: str, unknown_roles: list[str], canonical_roles: list[str]) -> UnrecognizedRoleSuggestionResponseSchema:
    client = genai.Client(api_key=api_key)
    prompt = build_prompt(unknown_roles, canonical_roles)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=UnrecognizedRoleSuggestionResponseSchema,
        temperature=0,
        system_instruction=prompt,
    )
    completion = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=".",
        config=config,
    )
    return UnrecognizedRoleSuggestionResponseSchema.model_validate_json(completion.text)


# ── GitHub helpers ───────────────────────────────────────────────────────────

def _generate_jwt(app_id: str, private_key: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"iat": now - 60, "exp": now + 600, "iss": app_id},
        private_key,
        algorithm="RS256",
    )


async def _get_github_token(app_id: str, private_key: str, installation_id: str) -> str:
    token = _generate_jwt(app_id, private_key)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        return resp.json()["token"]


async def open_roles_pr(novel_roles: list[str], repo_url: str, app_id: str, private_key: str, installation_id: str) -> str:
    """Add stub entries for novel roles to roles.yml and open a PR. Returns the PR URL."""
    token = await _get_github_token(app_id, private_key, installation_id)
    owner_repo = repo_url.rstrip("/").split("github.com/")[-1]

    async with httpx.AsyncClient(headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }) as client:
        # Get current file
        resp = await client.get(f"https://api.github.com/repos/{owner_repo}/contents/{ROLES_YML_PATH}")
        resp.raise_for_status()
        file_data = resp.json()
        current_content = base64.b64decode(file_data["content"]).decode()
        sha = file_data["sha"]

        # Append stubs
        stubs = "\n".join(
            f"  - role: {role}\n    is_unique: false  # TODO: verify"
            for role in novel_roles
        )
        new_content = current_content.rstrip() + "\n" + stubs + "\n"

        # Create branch
        branch = f"unrecognized-roles-{int(time.time())}"
        main_sha_resp = await client.get(f"https://api.github.com/repos/{owner_repo}/git/ref/heads/main")
        main_sha_resp.raise_for_status()
        main_sha = main_sha_resp.json()["object"]["sha"]
        await client.post(
            f"https://api.github.com/repos/{owner_repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": main_sha},
        )

        # Commit
        await client.put(
            f"https://api.github.com/repos/{owner_repo}/contents/{ROLES_YML_PATH}",
            json={
                "message": f"Add {len(novel_roles)} unrecognized role stub(s) to roles.yml",
                "content": base64.b64encode(new_content.encode()).decode(),
                "sha": sha,
                "branch": branch,
            },
        )

        # Open PR
        pr_resp = await client.post(
            f"https://api.github.com/repos/{owner_repo}/pulls",
            json={
                "title": f"Add {len(novel_roles)} unrecognized role stub(s)",
                "body": "Auto-generated by process_unrecognized_roles.py\n\nNovel roles:\n"
                        + "\n".join(f"- `{r}`" for r in novel_roles),
                "head": branch,
                "base": "main",
            },
        )
        pr_resp.raise_for_status()
        return pr_resp.json()["html_url"]


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    db_url = os.environ["CIVICPATCH_API_DB_URL"]
    gemini_api_key = os.environ["GOOGLE_GEMINI_TOKEN"]
    app_id = os.environ["GITHUB_APP_ID"]
    private_key = base64.b64decode(os.environ["GITHUB_APP_PRIVATE_KEY_BASE64"]).decode()
    installation_id = os.environ["GITHUB_APP_INSTALLATION_ID"]
    open_data_repo_url = os.environ["OPEN_DATA_REPO_URL"]

    with open(ROLES_YML_PATH) as f:
        canonical_roles = [r["role"] for r in yaml.safe_load(f)["roles"]]

    pool = AsyncConnectionPool(db_url, open=False, min_size=1, max_size=2)
    await pool.open()

    try:
        pending = await get_pending_roles(pool)
        if not pending:
            logger.info("No pending unrecognized roles.")
            return

        unknown_roles = [r["role"] for r in pending]
        logger.info("Processing %d unrecognized roles via Gemini", len(unknown_roles))

        result = call_gemini(gemini_api_key, unknown_roles, canonical_roles)

        matched = [s.role for s in result.suggestions if s.canonical_match]
        novel = [s.role for s in result.suggestions if not s.canonical_match]

        if matched:
            await update_roles_status(pool, matched, "suggested")
            logger.info("Marked %d roles as suggested", len(matched))

        if novel:
            logger.info("Opening PR for %d novel roles: %s", len(novel), novel)
            pr_url = await open_roles_pr(novel, open_data_repo_url, app_id, private_key, installation_id)
            await update_roles_status(pool, novel, "pr_opened", pr_url=pr_url)
            logger.info("PR opened: %s", pr_url)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
