from typing import Any, List
import github_service


def get_people_from_repo(jurisdiction_ocdid: str) -> List[Any]:
    data = github_service.get_github_file_contents("", file_path)
    return data
