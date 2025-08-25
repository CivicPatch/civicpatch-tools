import os
import requests
from schemas import PipelineContext



GITHUB_WORKFLOW_DISPATCH_URL = "https://api.github.com/repos/your-username/your-repo/actions/workflows/your-workflow.yml/dispatches"

def maybe_send_to_github(context: PipelineContext):
  # https://docs.github.com/en/rest/actions/workflows?apiVersion=2022-11-28#create-a-workflow-dispatch-event
  # https://github.com/android-sms-gateway/example-webhooks-fastapi/blob/master/main.py
  token = os.getenv("GITHUB_TOKEN_WITH_ACTIONS_PERMISSION")
  if not token:
    print("GITHUB_TOKEN_WITH_ACTIONS_PERMISSION is not set, skipping github workflow dispatch.")
    print("This is expected if you don't have permissions to trigger GitHub Actions on the civicpatch-tools repo.")
    print("Data will be collected via cron job as a fallback on the /github-actions endpoint.")
  
  headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {token}",
    "X-GitHub-Api-Version": "2022-11-28"
  }

  payload = {
    "server_name": "LOCAL_TEST_SERVER"
  }

  response = requests.post(GITHUB_WORKFLOW_DISPATCH_URL, headers=headers, json=payload)
  print("Response from GitHub workflow dispatch:", response.status_code, response.text)
  # Expected response code is 204

  return {}
  


