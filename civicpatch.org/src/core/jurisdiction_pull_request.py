import base64

import httpx

import environment
import shared.utils.id_utils as id_utils
from lib.github.auth import get_default_headers, get_jurisdictions_sync_headers
from lib.github.pull_requests import PrAuthor, open_attributed_pr
from lib.yaml_utils import yaml_dump, yaml_load


def _get_jurisdictions_repo_url() -> str:
    return environment.get_env_vars()["JURISDICTIONS_REPO_URL"]


def _get_jurisdictions_fork_repo_url() -> str:
    return environment.get_env_vars()["JURISDICTIONS_FORK_REPO_URL"]


def _extract_state(jurisdiction_ocdid: str) -> str:
    for part in jurisdiction_ocdid.split("/"):
        if part.startswith("state:"):
            return part.split(":")[1]
    raise ValueError(f"Cannot extract state from: {jurisdiction_ocdid}")


def _apply_fields(entry: dict, fields: dict) -> None:
    for key in ("url", "population", "geoid"):
        if fields.get(key) is not None:
            entry[key] = fields[key]


async def open_jurisdiction_edit_pr(
    jurisdiction_ocdid: str,
    fields: dict,
    author: PrAuthor,
) -> tuple[int, str] | tuple[None, str]:
    repo_url = _get_jurisdictions_repo_url()
    fork_repo_url = _get_jurisdictions_fork_repo_url()
    state = _extract_state(jurisdiction_ocdid)
    file_path = f"data/{state}/local/jurisdictions.yml"

    auth_headers = await get_jurisdictions_sync_headers()
    fork_auth_headers = await get_default_headers()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{repo_url}/contents/{file_path}",
            headers=auth_headers,
        )
    if response.status_code == 404:
        entries = [{"id": jurisdiction_ocdid}]
        _apply_fields(entries[0], fields)
    elif response.status_code != 200:
        return None, f"Failed to fetch {file_path}: {response.json().get('message', 'unknown')}"
    else:
        raw = base64.b64decode(response.json()["content"]).decode("utf-8")
        entries = yaml_load(raw)

        updated = False
        for entry in entries:
            if entry.get("id") == jurisdiction_ocdid:
                _apply_fields(entry, fields)
                updated = True
                break

        if not updated:
            return None, f"Jurisdiction {jurisdiction_ocdid} not found in {file_path}"

    content_str = yaml_dump(entries)
    branch_name = f"civicpatch/jurisdiction-edit/{id_utils.make_request_id()}"

    return await open_attributed_pr(
        branch_name=branch_name,
        file_path=file_path,
        content=content_str,
        commit_message=f"Update metadata: {jurisdiction_ocdid}",
        pull_request_title=f"Jurisdiction edit: {state}/{jurisdiction_ocdid.split('/')[-2]}",
        pull_request_body=f"Updating metadata for `{jurisdiction_ocdid}`.",
        author=author,
        repo_url=repo_url,
        fork_repo_url=fork_repo_url,
        headers=auth_headers,
        fork_headers=fork_auth_headers,
    )
