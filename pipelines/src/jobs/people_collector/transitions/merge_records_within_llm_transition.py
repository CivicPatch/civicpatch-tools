from typing import Dict, List
from jobs.people_collector.schemas import Person

def check_pipeline_heuristics(
        people_by_llm: Dict[str, List[Person]],
) -> tuple[bool, list[str]]:
    # Heuristic 1: if there are no records, fail
    if not people_by_llm or all(not people for people in people_by_llm.values()):
        return False, ["No records found by any LLM"]

    # Heuristic 2: Call "review_utils"
    return True, []