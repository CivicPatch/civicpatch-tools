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

  format_output = context.data.format_output_step
  save_data_to_file(format_output.officials, data_file_path)
  save_config_to_file(format_output.config, context.data.jurisdiction_ocdid)

  await update_people_job_result(logger, context.request_id, format_output.officials)

def save_data_to_file(people: List[Official], file_path: str):
    # Create parent directories if not exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        yaml.dump([official.model_dump() for official in people], f, sort_keys=False, allow_unicode=True)

def save_config_to_file(config: WorkflowConfig, jurisdiction_ocdid: str):
    config_file_path = data_path_utils.get_config_file_path(jurisdiction_ocdid)
    os.makedirs(os.path.dirname(config_file_path), exist_ok=True)
    with open(config_file_path, "w") as f:
        yaml.dump(config.model_dump(), f, sort_keys=False, allow_unicode=True)