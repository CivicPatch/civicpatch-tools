from typing import List

from runners.people_collector.schemas import ResearchedPerson
from shared.utils.taxonomy import Taxonomy, resolve_role


def filter_people_by_roles(
    people: List[ResearchedPerson], taxonomy: Taxonomy
) -> List[ResearchedPerson]:
    return [p for p in people if any(resolve_role(r, taxonomy) for r in p.roles)]
