import os
from typing import List
from domain.models import Person
from jobs.people_collector.schemas import (
  WorkflowStatus,
  WorkflowConfig,
  PeopleCollectorContext
)
import utils.log_utils
from shared.utils import data_path_utils 
import yaml

def save_output(context: PeopleCollectorContext):
  logger = utils.log_utils.get_workflow_logger(context.data.jurisdiction_id)
  logger.info(f"Step 8: {WorkflowStatus.CLEANUP} Saving output data and config files.")

  data_file_path = data_path_utils.get_data_file_path(
    context.data.jurisdiction_id
  )
  config_file_path = data_path_utils.get_config_file_path(
      context.data.jurisdiction_id
  )

  people = context.data.merge_records_across_llms_step.people
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

def save_data_to_file(people: List[Person], file_path: str):
    # Create parent directories if not exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        yaml.dump([person.model_dump() for person in people], f)

def save_config_to_file(config: WorkflowConfig, file_path: str):
    with open(file_path, "w") as f:
        yaml.dump(config.model_dump(), f)
