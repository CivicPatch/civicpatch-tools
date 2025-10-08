import os
import requests
import zipfile
from schemas import PipelineContext, PipelineStatus

from utils.request_utils import with_retry
from utils.data_path_utils import get_data_municipality_path, get_data_source_municipality_path
from utils import id_utils, log_utils, cost_utils

GITHUB_WORKFLOW_DISPATCH_URL = "https://api.github.com/repos/your-username/your-repo/actions/workflows/your-workflow.yml/dispatches"

def maybe_send_to_github(context: PipelineContext):
  logger = log_utils.get_pipeline_logger(context["jurisdiction_id"])
  logger.info(f"Step 5: {PipelineStatus.MAYBE_SEND_TO_GITHUB.value}")

  # https://docs.github.com/en/rest/actions/workflows?apiVersion=2022-11-28#create-a-workflow-dispatch-event
  # https://github.com/android-sms-gateway/example-webhooks-fastapi/blob/master/main.py
  CRUDDER_SHARED_TOKEN = os.getenv("CRUDDER_SHARED_TOKEN")
  CRUDDER_URL = os.getenv("CRUDDER_URL", "https://crudder.civicpatch.org")
  CRUDDER_UPLOAD_URL = f"{CRUDDER_URL}/api/github_intake"
  logger.info(f"CRUDDER_UPLOAD_URL: {CRUDDER_UPLOAD_URL}")

  try:
    if not CRUDDER_SHARED_TOKEN:
      logger.error("CRUDDER_SHARED_TOKEN is not set, skipping github workflow dispatch.")
      logger.error(f"Generate api key from CRUDDER at {CRUDDER_URL}")

      return {
        "steps": {
          **context["steps"],
          PipelineStatus.MAYBE_SEND_TO_GITHUB.value: {
              "status": "skipped"
          }
        }
      }

    zip_file_path = zip_files(context["request_id"], context["jurisdiction_id"])
    zip_file_size = os.path.getsize(zip_file_path)
    logger.info(f"Created zip file at {zip_file_path}, size: {zip_file_size} bytes")
    cost_utils.add_storage_cost(
        context["jurisdiction_id"], 
        file_size_bytes=zip_file_size
    )

    headers = {
      "Authorization": CRUDDER_SHARED_TOKEN,
    }
  
    files = {
        'file': (os.path.basename(zip_file_path), open(zip_file_path, 'rb'), 'application/zip')
    }

    # Add metadata in the request body
    data = {
       "request_id": context["request_id"],
       "jurisdiction_id": context["jurisdiction_id"],
    } 

    response = with_retry(
        logger,
        max_retries=5, 
        func=lambda: requests.post(
            CRUDDER_UPLOAD_URL, 
            headers=headers, 
            files=files,
            data=data
        )
    )

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
  except Exception as e:
    logger.error(f"Error sending to Crudder: {e}")
    return {
      "steps": {
        **context["steps"],
        PipelineStatus.MAYBE_SEND_TO_GITHUB.value: {
            "status": "failed",
            "error": str(e)
        }
      }
    }

def zip_files(request_id, jurisdiction_id):
    data_municipality_path = get_data_municipality_path(jurisdiction_id)
    data_source_municipality_path = get_data_source_municipality_path(jurisdiction_id)

    git_branch_name= id_utils.jurisdiction_id_to_git_branch(jurisdiction_id, request_id)
    zip_file_name = f"{git_branch_name}.zip"
    zip_file_path = os.path.join("crudder_data", zip_file_name)

    # Find the common parent directory
    common_prefix = os.path.commonpath([data_municipality_path, data_source_municipality_path])

    with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for folder_path in [data_municipality_path, data_source_municipality_path]:
            for root, _dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    # arcname will include data/ or data_source/ as the top-level folder
                    arcname = os.path.relpath(file_path, common_prefix)
                    zipf.write(file_path, arcname)

    return zip_file_path