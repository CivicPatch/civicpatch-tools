import os
import shutil
from jobs.people_collector.schemas import PeopleCollectorContext, WorkflowStatus
from shared.utils.data_path_utils import get_cache_path, get_images_path
from utils import log_utils

def prepare_pipeline(context: PeopleCollectorContext) -> None:
    """
    Prepare the pipeline context for the next steps.
    """
    jurisdiction_ocdid = context.data.jurisdiction_ocdid

    # Empty log file, if it exists
    logger = log_utils.get_workflow_logger(jurisdiction_ocdid)
    logger.clear()

    logger.info(f"Step 0: {WorkflowStatus.INIT.value}")

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