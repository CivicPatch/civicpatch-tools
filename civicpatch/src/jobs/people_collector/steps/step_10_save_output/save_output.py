import os
from typing import List
from domain.models import Official
from jobs.people_collector.schemas import (
  WorkflowStatus,
  WorkflowConfig,
  PeopleCollectorContext
)
import utils.log_utils
from shared.utils import data_path_utils 
import yaml
from services.civicpatch_api import update_people_job_result
import datetime
from datetime import timezone, datetime

async def save_output(context: PeopleCollectorContext):
  logger = utils.log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
  logger.info(f"Step 10: {WorkflowStatus.SAVE_OUTPUT} Saving output data and config files.")

  data_file_path = data_path_utils.get_data_file_path(
    context.data.jurisdiction_ocdid
  )
  config_file_path = data_path_utils.get_config_file_path(
      context.data.jurisdiction_ocdid
  )
  metadata_file_path = data_path_utils.get_metadata_file_path(
      context.data.jurisdiction_ocdid
  )

  format_output = context.data.format_output_step
  save_data_to_file(format_output.officials, data_file_path)

  updated_config = format_output.config

  save_config_to_file(updated_config, config_file_path)
  await update_people_job_result(logger, context.request_id, format_output.officials)

  save_metadata_to_file(context, metadata_file_path)

def save_data_to_file(people: List[Official], file_path: str):
    # Create parent directories if not exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        yaml.dump([official.model_dump() for official in people], f, sort_keys=False, allow_unicode=True)

def save_config_to_file(config: WorkflowConfig, file_path: str):
    with open(file_path, "w") as f:
        yaml.dump(config.model_dump(), f, sort_keys=False, allow_unicode=True)

def save_metadata_to_file(context: PeopleCollectorContext, file_path: str):
  metadata = {
     "created_at": context.created_at,
     "updated_at": context.updated_at
  }

  with open(file_path, "w") as f:
      yaml.dump(metadata, f, sort_keys=False, allow_unicode=True)