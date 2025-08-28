import os
import requests
import zipfile
from schemas import PipelineStatus

from utils.data_path_utils import get_data_municipality_path, get_data_source_municipality_path
from schemas import PipelineContext

GITHUB_WORKFLOW_DISPATCH_URL = "https://api.github.com/repos/your-username/your-repo/actions/workflows/your-workflow.yml/dispatches"

def maybe_send_to_github(context: PipelineContext):
  # https://docs.github.com/en/rest/actions/workflows?apiVersion=2022-11-28#create-a-workflow-dispatch-event
  # https://github.com/android-sms-gateway/example-webhooks-fastapi/blob/master/main.py
  CRUDDER_SHARED_TOKEN = os.getenv("CRUDDER_SHARED_TOKEN")
  CRUDDER_URL = os.getenv("CRUDDER_URL", "https://crudder.civicpatch.org")
  CRUDDER_UPLOAD_URL = f"{CRUDDER_URL}/github_intake"

  if not CRUDDER_SHARED_TOKEN:
    print("CRUDDER_SHARED_TOKEN is not set, skipping github workflow dispatch.")
    print(f"Generate api key from CRUDDER at {CRUDDER_URL}")

    return {
      "steps": {
        **context["steps"],
        PipelineStatus.MAYBE_SEND_TO_GITHUB.value: {
            "status": "skipped"
        }
      }
    }

  zip_file_path = zip_files(context["request_id"], context["state"], context["geoid"])

  headers = {
    "Authorization": CRUDDER_SHARED_TOKEN,
  }
  
  files = {
    'file': (os.path.basename(zip_file_path), open(zip_file_path, 'rb'), 'application/zip')
  }

  response = requests.post(CRUDDER_UPLOAD_URL, headers=headers, files=files)

  return {
    "steps": {
      **context["steps"],
      PipelineStatus.MAYBE_SEND_TO_GITHUB.value: {
          "status": "completed" if response.status_code == 200 else "failed",
          "response_status_code": response.status_code,
          "response_text": response.text
      }
    }
  }

def zip_files(request_id, state, geoid):
  # Get all files under get_data_municipality_path(state, geoid) and get_data_source_municipality_path(state, geoid)
  # Zip them up under folder /crudder_data
  # Name it request_payload_{state}_{geoid}_{generated_uuid}.zip
  data_municipality_path = get_data_municipality_path(state, geoid)
  data_source_municipality_path = get_data_source_municipality_path(state, geoid)
  zip_file_name = f"request_payload_{state}_{geoid}_{request_id}.zip"
  zip_file_path = os.path.join("crudder_data", zip_file_name)

  with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, _dirs, files in os.walk(data_municipality_path):
      for file in files:
        file_path = os.path.join(root, file)
        arcname = os.path.relpath(file_path, data_municipality_path)
        zipf.write(file_path, arcname)

    for root, _dirs, files in os.walk(data_source_municipality_path):
      for file in files:
        file_path = os.path.join(root, file)
        arcname = os.path.relpath(file_path, data_source_municipality_path)
        zipf.write(file_path, arcname)
  
  return zip_file_path