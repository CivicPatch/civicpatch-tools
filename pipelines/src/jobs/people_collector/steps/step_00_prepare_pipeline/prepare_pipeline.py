import os
import shutil
from jobs.people_collector.schemas import PeopleCollectorContext, PipelineStatus
from shared.utils.data_path_utils import get_cache_path, get_images_path
from utils import log_utils

async def prepare_pipeline(context: PeopleCollectorContext) -> None:
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 0: {PipelineStatus.INIT.value}")

    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    logger.clear()

    reset_folder(get_cache_path(jurisdiction_ocdid))
    reset_folder(get_images_path(jurisdiction_ocdid))

def reset_folder(path: str) -> None:
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)
