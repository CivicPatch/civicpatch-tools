from datetime import datetime
from typing import List
from schemas import ResearchedPerson
import shared.utils.config_utils as config_utils

def municipality_officials_prompt(people_hint: List[ResearchedPerson]):
    """
    Generate a prompt to identify municipality officials from the given content.
    """
    roles = config_utils.get_role_names()
    designation_names = config_utils.get_designation_names()
    designations_str = ", ".join(designation_names)


    hint_str = ""
    if people_hint:
        hint_names = [person.name for person in people_hint if person.name]
        if hint_names:
            hint_str = "Here are the list of known target people (may be missing or include a few extra): " + ", ".join(hint_names) + "."

    prompt = f"""
Extract municipality officials (ex: mayors and council members, or equivalent positions for the government type), if found, 
from the markdown text. {hint_str}

Target roles: {', '.join(roles)}
Target designations: {designations_str}

Return JSON array of people with:
- name: (String) Full name only
- roles: (Array) Official titles
- designations: (Array) 
    Example: "Ward 1", "District 2, Seat 8"
- image: (String|null) Photo URL (.jpg/.png)
- website: (String or null) Use the official's profile or biography URL if available; otherwise, use a contact form URL. If neither exists, set to null.
- phone_number: (String|null) Contact number
- email: (String|null) Email address
- start_date: (String|null) YYYY[-MM[-DD]]
- end_date: (String|null) YYYY[-MM[-DD]]

URLs: Include profile/bio pages. Exclude news/events/press.
Terms: "2024-2027" → start: "2024", end: "2027"
Designations: Extract exactly from text -- do not infer or make up designations.
"""
    return prompt