import os
from typing import List
from domain.models import Official
from jobs.people_collector.schemas import (
  PipelineStatus,
  PeopleCollectorContext
)
import utils.log_utils
from shared.utils import data_path_utils
import yaml

async def save_output(context: PeopleCollectorContext):
  logger = utils.log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
  logger.info(f"Step 10: {PipelineStatus.SAVE_OUTPUT} Saving output data and config files.")

  data_file_path = data_path_utils.get_data_file_path(
    context.data.jurisdiction_ocdid
  )

  format_output = context.data.format_output_step
  assert format_output is not None, "should never happen — format_output_step is required before save_output"
  save_data_to_file(format_output.officials, data_file_path)

def save_data_to_file(people: List[Official], file_path: str):
    # Create parent directories if not exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        yaml.dump([official.model_dump() for official in people], f, sort_keys=False, allow_unicode=True)
