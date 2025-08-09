import os
import shutil
from schemas import PipelineContext, PipelineStatus
from utils.data_path_utils import get_cache_path, get_people_path, get_images_path

def prepare_pipeline(context: PipelineContext):
    """
    Prepare the pipeline context for the next steps.
    """
    print(f"Preparing pipeline for state: {context['state']}, GEOID: {context['geoid']}, step: 'prepare_pipeline'")
    print(f"Step 0: {PipelineStatus.INIT.value}")

    # Create/clear cache folder
    cache_path = get_cache_path(context["state"], context["geoid"])
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)  # Recursively delete all files and subdirectories
    os.makedirs(cache_path, exist_ok=True)  # Recreate the folder

    # Create/clear people folder
    people_path = get_people_path(context["state"], context["geoid"])
    if os.path.exists(people_path):
        shutil.rmtree(people_path)  # Recursively delete all files and subdirectories
    os.makedirs(people_path, exist_ok=True)  # Recreate the folder

    # Create/cleap images folder
    images_path = get_images_path(context["state"], context["geoid"])
    if os.path.exists(images_path):
        shutil.rmtree(images_path)
    os.makedirs(images_path, exist_ok=True)  # Recreate the folder

    return {}