import os
import shutil

from utils.data_path_utils import get_data_source_municipality_path
from schemas import PipelineContext, PipelineStatus

def cleanup(context: PipelineContext):
    # Remove files under data_source/cache and data_source/images
    print(f"Step 9: {PipelineStatus.CLEANUP.value}")
    data_source_dir = get_data_source_municipality_path(context["state"], context["geoid"])
    cache_dir = os.path.join(data_source_dir, "cache")
    images_dir = os.path.join(data_source_dir, "images")

    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
    if os.path.exists(images_dir):
        shutil.rmtree(images_dir)

    return {}