from typing import Any, List

import github_service
import schemas


def get_people_from_repo(jurisdiction_ocdid: str) -> List[Any]:
    file_path = schemas.jurisdiction_id_to_folder(jurisdiction_ocdid)
    data = github_service.get_github_file_contents(f"data/{file_path}")
    return data
