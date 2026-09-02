import os
from typing import List
from shared.schemas import PersonSourceRecord
from runners.people_collector.schemas import (
  PipelineStatus,
  PeopleCollectorContext
)
import utils.log_utils
from shared.utils import data_path_utils
from shared.utils.yaml_utils import yaml_dump

async def save_output(context: PeopleCollectorContext):
  logger = utils.log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
  logger.info(f"Step 6: {PipelineStatus.SAVE_OUTPUT} Saving output data and config files.")

  data_file_path = data_path_utils.get_data_file_path(
    context.data.jurisdiction_ocdid
  )

  process_step = context.data.process_page_content_step
  assert process_step is not None, "should never happen — process_page_content_step is required before save_output"
  save_data_to_file(process_step.all_records(), data_file_path)


def save_data_to_file(records: List[PersonSourceRecord], file_path: str):
    """One row per sighting, labels verbatim, each stamped with the page it came from.

    Not a roster: several rows can describe one person, and which ones do is cp.org's to
    decide.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        f.write(yaml_dump([record.model_dump() for record in records]))
