import os
from typing import List, Optional, Dict, Any
import yaml
import base64
import httpx

from schemas.common import PullRequest
timeout = httpx.Timeout(60.0)  
github_async_client = httpx.AsyncClient(timeout=timeout)

GITHUB_WORKFLOW_TOKEN = os.getenv("GITHUB_WORKFLOW_TOKEN")
GITHUB_UPDATE_TOKEN = os.getenv("GITHUB_UPDATE_TOKEN")

# Shared HTTP client
github_async_client = httpx.AsyncClient(timeout=timeout)

def get_default_headers() -> Dict[str, str]:
    """
    Get the default headers for GitHub API requests.
    """
    return {
        "Authorization": f"Bearer {GITHUB_WORKFLOW_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

async def trigger_people_job_workflow(
    request_id: str,
    jurisdiction_ocdid: str,
    name: str | None = None,
    url: str | None = None,
):
    data = {
        "ref": "main",
        "inputs": {
            "request_id": request_id,
            "jurisdiction_ocdid": jurisdiction_ocdid,
        }
    }

    if name:
        data["inputs"]["name"] = name
    if url:
        data["inputs"]["url"] = url

    headers = {
        **get_default_headers(),
        "Accept": "application/vnd.github+json",
    }


    response = await github_async_client.post(
        "https://api.github.com/repos/CivicPatch/server/actions/workflows/data_scrape.yml/dispatches",
        headers=headers,
        json=data,
    )

    print("Response from GitHub API:", response.status_code, response.text)

    if response.status_code != 204:
        raise Exception(
            f"Failed to trigger workflow: {response.status_code} - {response.text}"
        )

    return True


async def trigger_github_data_intake_workflow(
    user_email: str,
    server_url: str,
    request_id: str,
    jurisdiction_ocdid: str,
    zip_file_url: str
):
    # Trigger GitHub Actions workflow to pull data from the given URL
    # For example, you might use the GitHub API to dispatch a workflow event
    data = {
        "ref": "main",
        "inputs": {
            "server_url": server_url,
            "user_email": user_email,
            "request_id": request_id,
            "jurisdiction_ocdid": jurisdiction_ocdid,
            "zip_file_url": zip_file_url
        },
    }

    headers = {
        **get_default_headers(),
         "Accept": "application/vnd.github+json",
    }

    response = await github_async_client.post(
            "https://api.github.com/repos/CivicPatch/open-data/actions/workflows/data_intake.yml/dispatches",
            headers=headers,
            json=data,
        )

    print("Response from GitHub API:", response.status_code, response.text)

    if response.status_code != 204:
        raise Exception(
            f"Failed to trigger workflow: {response.status_code} - {response.text}"
        )

    return True


async def get_github_file_contents(
        github_file_path: str,
        ref: Optional[str] = None,
    ) -> str | None:
    print("Fetching GitHub file:", github_file_path, "ref:", ref)

    url = (
        f"https://api.github.com/repos/CivicPatch/open-data/contents/{github_file_path}"
    )
    if ref:
        url += f"?ref={ref}"    
    headers = {
        **get_default_headers(),
        "Accept": "application/vnd.github.raw",
    }
    response = await github_async_client.get(url, headers=headers, timeout=timeout)

    if response.status_code == 200:
        file_content = response.text
        return file_content
    else:
        print(f"Error fetching file contents: {github_file_path}", response.status_code, response.text)
        return None


async def get_open_pull_requests() -> List[PullRequest]:
    params = "state=open&per_page=100&sort=created&direction=desc"
    url = f"https://api.github.com/repos/CivicPatch/open-data/pulls?{params}"


    headers = {
        **get_default_headers(),
        "Accept": "application/vnd.github+json",
    }

    response = await github_async_client.get(url, headers=headers, timeout=timeout)

    if response.status_code == 200:
        pull_requests = response.json()
        valid_pull_requests = [
            PullRequest(
                branch_name=pr["head"]["ref"],
                url=pr["html_url"],
            ) for pr in pull_requests
        ]
        return [pr for pr in valid_pull_requests if pr.jurisdiction_ocdid]
    else:
        print("Error fetching pull requests:", response.status_code, response.text)
        return []
    
async def get_open_pull_request_by_branch_suffix(suffix: str) -> List[PullRequest]:
    pull_requests = await get_open_pull_requests()
    matching_prs = [pr for pr in pull_requests if pr.branch_name.endswith(suffix)]
    return matching_prs

async def update_pull_request_file(
    branch_name: str,
    file_path: str,
    new_data: List[Dict[str, Any]],
    commit_message: str = "Automated update via API"
) -> bool:
    # Get file SHA
    contents_url = f"https://api.github.com/repos/CivicPatch/open-data/contents/{file_path}?ref={branch_name}"
    print("Content url:", contents_url)
    contents_response = await github_async_client.get(contents_url, headers=headers, timeout=timeout)
    if contents_response.status_code != 200:
        print("Error fetching file contents:", contents_response.status_code, contents_response.text)
        return False
    sha = contents_response.json()["sha"]
    print("sha:", sha)
    serialized_data = yaml.dump(new_data, sort_keys=False, allow_unicode=True)
    encoded_content = base64.b64encode(serialized_data.encode("utf-8")).decode("utf-8")

    data = {
        "message": commit_message,
        "content": encoded_content,
        "sha": sha,
        "branch": branch_name
    }

    headers = {
        **get_default_headers(),
         "Accept": "application/vnd.github+json",
    }

    # Update file
    update_response = await github_async_client.put(contents_url, json=data)
    if update_response.status_code in [200, 201]:
        print("File updated successfully.")
        return True
    else:
        print("Error updating file:", update_response.status_code, update_response.text)
        return False
