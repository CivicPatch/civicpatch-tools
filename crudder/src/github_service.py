import requests

def trigger_github_data_intake_workflow(
        github_workflow_token, 
        user_email: str, 
        server_url: str, 
        request_id: str, 
        jurisdiction_id: str, 
        zip_file_url: str):
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
            "zip_file_url": zip_file_url
        }
    }
    
    response = requests.post(
        "https://api.github.com/repos/CivicPatch/open-data/actions/workflows/yy_data_intake.yml/dispatches",
        headers=headers,
        json=data
    )

    print("Response from GitHub API:", response.status_code, response.text)
    
    if response.status_code != 204:
        raise Exception(f"Failed to trigger workflow: {response.status_code} - {response.text}")
    
    return True