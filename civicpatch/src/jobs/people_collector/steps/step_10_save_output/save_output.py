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

def save_output(context: PeopleCollectorContext):
  logger = utils.log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
  logger.info(f"Step 8: {WorkflowStatus.CLEANUP} Saving output data and config files.")

  data_file_path = data_path_utils.get_data_file_path(
    context.data.jurisdiction_ocdid
  )
  config_file_path = data_path_utils.get_config_file_path(
      context.data.jurisdiction_ocdid
  )

  people = context.data.format_output_step
  save_data_to_file(people, data_file_path)

  updated_config = WorkflowConfig(
    url=context.data.config.url,
    name=context.data.config.name,
    
    # TODO: might not want to save this?
    source_urls=context.data.config.source_urls,
    
    identities=context.data.identities, # Can be updated up via job
    government_type=context.data.research_municipality_step.government_type # Can be updated via research step if config not available
  )
  save_config_to_file(updated_config, config_file_path)

def save_data_to_file(people: List[Official], file_path: str):
    # Create parent directories if not exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        yaml.dump([official.model_dump() for official in people], f, sort_keys=False, allow_unicode=True)

def save_config_to_file(config: WorkflowConfig, file_path: str):
    with open(file_path, "w") as f:
        yaml.dump(config.model_dump(), f, sort_keys=False, allow_unicode=True)
