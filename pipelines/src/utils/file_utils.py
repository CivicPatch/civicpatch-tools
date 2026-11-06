import os
import tempfile
import zipfile

from shared.schemas import LLMCall
from shared.utils import id_utils
from utils.cost_utils import costs_json

CONTEXT_FILE = "context.json"
COSTS_FILE = "costs.json"
from shared.utils.data_path_utils import (
    get_data_file_path,
    get_data_source_path_for_jurisdiction_ocdid,
)


def zip_job_artifacts(pipeline_run_id: str, jurisdiction_ocdid: str, include_data: bool = True) -> str:
    data_source_path = get_data_source_path_for_jurisdiction_ocdid(jurisdiction_ocdid)
    git_branch_name = id_utils.make_git_branch(jurisdiction_ocdid, pipeline_run_id)
    zip_file_path = os.path.join("crudder_data", f"{git_branch_name}.zip")
    os.makedirs(os.path.dirname(zip_file_path), exist_ok=True)

    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _dirs, files in os.walk(data_source_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = f"data_source/{os.path.relpath(file_path, data_source_path.split('data_source/')[0] + 'data_source/')}"
                zipf.write(file_path, arcname)

        if include_data:
            data_file_path = get_data_file_path(jurisdiction_ocdid)
            if os.path.exists(data_file_path):
                data_dir = data_file_path.split("data/")[0] + "data/"
                zipf.write(data_file_path, f"data/{os.path.relpath(data_file_path, data_dir)}")

    return zip_file_path


def zip_run_context(pipeline_run_id: str, jurisdiction_ocdid: str, context_json: str, calls: list[LLMCall]) -> str:
    """A collector run's upload: its context and its model calls, nothing from disk."""
    zip_file_path = os.path.join(tempfile.mkdtemp(), f"{id_utils.make_git_branch(jurisdiction_ocdid, pipeline_run_id)}.zip")
    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(CONTEXT_FILE, context_json)
        zipf.writestr(COSTS_FILE, costs_json(calls))
    return zip_file_path
