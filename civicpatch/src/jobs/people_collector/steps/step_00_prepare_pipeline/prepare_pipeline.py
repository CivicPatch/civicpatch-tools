import os
import shutil
from jobs.people_collector.schemas import PeopleCollectorContext, PreparePipelineStep, WorkflowStatus
from shared.utils.data_path_utils import get_cache_path, get_images_path
from services.civicpatch_api import search_people
from utils import log_utils

async def prepare_pipeline(context: PeopleCollectorContext) -> PreparePipelineStep:
    """
    Prepare the pipeline context for the next steps.

    This includes:
    - Registering the job with api.civicpatch.org, if applicable.
    - Emptying the log file for the jurisdiction.
    """
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 0: {WorkflowStatus.INIT.value}")

    jurisdiction_ocdid = context.data.jurisdiction_ocdid

    # Empty log file, if it exists
    logger = log_utils.get_workflow_logger(jurisdiction_ocdid)
    logger.clear()

    # Create/clear cache folder
    cache_path = get_cache_path(jurisdiction_ocdid)
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)  # Recursively delete all files and subdirectories
    os.makedirs(cache_path, exist_ok=True)  # Recreate the folder

    # Create/clear images folder
    images_path = get_images_path(jurisdiction_ocdid)
    if os.path.exists(images_path):
        shutil.rmtree(images_path)
    os.makedirs(images_path, exist_ok=True)  # Recreate the folder

    existing_people = await search_people(jurisdiction_ocdid, state="current")
    logger.info(f"prepare_pipeline: {len(existing_people)} current people found in DB.")

    return PreparePipelineStep(existing_people=existing_people)