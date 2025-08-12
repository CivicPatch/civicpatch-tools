from typing import List, Dict
from schemas import LLMPerson, ProcessedLLMPeople, PeopleByNameDict
from nameparser import HumanName

def group_people_by_name(
    people_by_name: PeopleByNameDict,
    people_to_link: List[LLMPerson]
) -> Dict[str, ProcessedLLMPeople]:
    """
    Returns a dict mapping normalized key to:
      { "names": list of all unique names seen, "records": list of LLMPerson }
    """
    def first_last_key(name: str) -> str:
        hn = HumanName(name)
        return f"{hn.first.strip().lower()} {hn.last.strip().lower()}"

    for person in people_to_link:
        key = first_last_key(person.name)
        if key not in people_by_name:
            people_by_name[key] = ProcessedLLMPeople(
                names=[],
                records=[]
            )
        if person.name not in people_by_name[key].names:
            people_by_name[key].names.append(person.name)
        people_by_name[key].records.append(person)


    return people_by_name
