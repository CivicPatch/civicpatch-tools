import os
from typing import List

import requests

from schemas import PullRequest

GITHUB_WORKFLOW_TOKEN = os.getenv("GITHUB_WORKFLOW_TOKEN")


def trigger_github_data_intake_workflow(
    github_workflow_token,
    user_email: str,
    server_url: str,
    request_id: str,
    jurisdiction_id: str,
    zip_file_url: str,
):
    # Trigger GitHub Actions workflow to pull data from the given URL
    # For example, you might use the GitHub API to dispatch a workflow event
    headers = {
        "Authorization": f"Bearer {github_workflow_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    data = {
        "ref": "main",
        "inputs": {
            "server_url": server_url,
            "user_email": user_email,
            "request_id": request_id,
            "jurisdiction_id": jurisdiction_id,
            "zip_file_url": zip_file_url,
        },
    }

    response = requests.post(
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


def get_github_file_contents(github_file_path: str) -> str | None:
    headers = {
        "Authorization": f"Bearer {GITHUB_WORKFLOW_TOKEN}",
        "Accept": "application/vnd.github.raw",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    url = (
        f"https://api.github.com/repos/CivicPatch/open-data/contents/{github_file_path}"
    )
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        file_content = response.text
        return file_content
    else:
        print("Error fetching file contents:", response.status_code, response.text)
        return None


def get_open_pull_requests(github_workflow_token: str) -> List[PullRequest]:
    headers = {
        "Authorization": f"Bearer {github_workflow_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    params = "state=open&per_page=100"
    url = f"https://api.github.com/repos/CivicPatch/open-data/pulls?{params}"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        pull_requests = response.json()
        return [PullRequest(branch_name=pr["head"]["ref"]) for pr in pull_requests]
    else:
        print("Error fetching pull requests:", response.status_code, response.text)
        return []
