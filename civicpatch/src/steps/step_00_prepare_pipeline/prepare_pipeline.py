import os
import shutil
from schemas import PipelineContext, PipelineStatus
from utils.data_path_utils import get_cache_path, get_images_path

def prepare_pipeline(context: PipelineContext):
    """
    Prepare the pipeline context for the next steps.
    """
    print(f"Step 0: {PipelineStatus.INIT.value}")

    jurisdiction_id = context["jurisdiction_id"]

    # Create/clear cache folder
    cache_path = get_cache_path(jurisdiction_id)
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)  # Recursively delete all files and subdirectories
    os.makedirs(cache_path, exist_ok=True)  # Recreate the folder

    # Create/clear images folder
    images_path = get_images_path(jurisdiction_id)
    if os.path.exists(images_path):
        shutil.rmtree(images_path)
    os.makedirs(images_path, exist_ok=True)  # Recreate the folder

    return context