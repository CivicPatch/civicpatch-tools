import base64
import logging
import time
from datetime import datetime, timezone
from typing import Dict

import httpx
import jwt

import environment
import lib.cache as cache_service

logger = logging.getLogger(__name__)

# Refresh cached installation tokens before GitHub actually expires them so a
# token can't die mid-request.
TOKEN_REFRESH_MARGIN_SECONDS = 300


def _get_github_config():
    env = environment.get_env_vars()
    app_id = env["GITHUB_APP_ID"]
    private_key = base64.b64decode(env["GITHUB_APP_PRIVATE_KEY_BASE64"]).decode()
    installation_id = env["GITHUB_APP_INSTALLATION_ID"]
    open_data_repo_url = env["OPEN_DATA_REPO_URL"]
    return app_id, private_key, installation_id, open_data_repo_url


def _generate_jwt() -> str:
    logger.debug("Generating JWT for GitHub App authentication.")
    app_id, private_key, _, _ = _get_github_config()
    now = int(time.time())
    return jwt.encode(
        {"iat": now - 60, "exp": now + 600, "iss": app_id},
        private_key,
        algorithm="RS256",
    )


async def _fetch_github_token() -> tuple[str, float]:
    logger.debug("Fetching new GitHub installation access token.")
    _, _, installation_id, _ = _get_github_config()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {_generate_jwt()}",
                "Accept": "application/vnd.github+json",
            },
        )
        response.raise_for_status()
        data = response.json()

    token = data["token"]
    expires_at = datetime.strptime(data["expires_at"], "%Y-%m-%dT%H:%M:%SZ")
    expires_at = expires_at.replace(tzinfo=timezone.utc).timestamp()
    logger.info(f"Fetched new GitHub token, expires at {expires_at}")
    return token, expires_at


async def get_github_token():
    _, _, installation_id, _ = _get_github_config()
    cache_key = f"github:installation:{installation_id}"
    logger.debug(f"Retrieving GitHub token from cache with key: {cache_key}")
    cached_token = await cache_service.get_cached(cache_key)
    if cached_token and "token" in cached_token:
        token = cached_token["token"]
        logger.debug("GitHub token found in cache.")
        return token
    logger.info("GitHub token not found in cache, fetching new token.")
    token, expires_at = await _fetch_github_token()
    ttl = max(1, int(expires_at - time.time()) - TOKEN_REFRESH_MARGIN_SECONDS)
    await cache_service.set_cached(cache_key, {"token": token}, ttl)
    return token


async def get_default_headers() -> Dict[str, str]:
    logger.debug("Building default headers for GitHub API requests.")
    github_token = await get_github_token()
    return {
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_jurisdictions_sync_config():
    env = environment.get_env_vars()
    app_id = env["JURISDICTIONS_SYNC_APP_ID"]
    private_key = base64.b64decode(env["JURISDICTIONS_SYNC_APP_PRIVATE_KEY_BASE64"]).decode()
    installation_id = env["JURISDICTIONS_SYNC_APP_INSTALLATION_ID"]
    return app_id, private_key, installation_id


def _generate_jurisdictions_sync_jwt() -> str:
    logger.debug("Generating JWT for jurisdictions-sync GitHub App authentication.")
    app_id, private_key, _ = _get_jurisdictions_sync_config()
    now = int(time.time())
    return jwt.encode(
        {"iat": now - 60, "exp": now + 600, "iss": app_id},
        private_key,
        algorithm="RS256",
    )


async def _fetch_jurisdictions_sync_token() -> tuple[str, float]:
    logger.debug("Fetching new jurisdictions-sync GitHub installation access token.")
    _, _, installation_id = _get_jurisdictions_sync_config()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {_generate_jurisdictions_sync_jwt()}",
                "Accept": "application/vnd.github+json",
            },
        )
        response.raise_for_status()
        data = response.json()

    token = data["token"]
    expires_at = datetime.strptime(data["expires_at"], "%Y-%m-%dT%H:%M:%SZ")
    expires_at = expires_at.replace(tzinfo=timezone.utc).timestamp()
    return token, expires_at


async def get_jurisdictions_sync_token() -> str:
    _, _, installation_id = _get_jurisdictions_sync_config()
    cache_key = f"github:installation:jurisdictions_sync:{installation_id}"
    cached_token = await cache_service.get_cached(cache_key)
    if cached_token and "token" in cached_token:
        return cached_token["token"]
    token, expires_at = await _fetch_jurisdictions_sync_token()
    ttl = max(1, int(expires_at - time.time()) - TOKEN_REFRESH_MARGIN_SECONDS)
    await cache_service.set_cached(cache_key, {"token": token}, ttl)
    return token


async def get_jurisdictions_sync_headers() -> Dict[str, str]:
    token = await get_jurisdictions_sync_token()
    return {
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
