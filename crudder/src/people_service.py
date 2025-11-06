import yaml
from typing import Any, List

import github_service
from schemas import Person


def get_people_from_repo(people_filepath: str) -> List[Person]:
    serialized_data = github_service.get_github_file_contents(f"{people_filepath}")
    data = yaml.safe_load(serialized_data)

    unserialized_data = [Person(**item) for item in data]
    return unserialized_data
