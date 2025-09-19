from datetime import datetime
import utils.config_utils as config_utils

def municipality_officials_prompt(government_type, people_hint):
    """
    Generate a prompt to identify municipality officials from the given content.
    """
    roles = config_utils.get_roles_by_government_type(government_type)
    # division_names = config_utils.get_divisions()
    # divisions_str = ", ".join(division_names)


    hint_str = ""
    if people_hint:
        hint_names = [person.get("name") for person in people_hint if person.get("name")]
        if hint_names:
            hint_str = "Here are the list of known target people (may be missing or include a few extra): " + ", ".join(hint_names) + "."

    prompt = f"""
Extract municipality officials (ex: mayors and council members, or equivalent positions for the government type), if found, 
from the markdown text. {hint_str}

Government type: '{government_type}'
Target roles: {', '.join(roles)}
Target divisions: ward, district 

Return JSON array of people with:
- name: (String) Full name only
- roles: (Array) Official titles
- divisions: (Array) Strictly districts/wards. 
    Example: "Ward 1", "District 2"
- image: (String|null) Photo URL (.jpg/.png)
- website: (String|null) Profile/bio page URL
- phone_number: (String|null) Contact number
- email: (String|null) Email address
- start_date: (String|null) YYYY[-MM[-DD]]
- end_date: (String|null) YYYY[-MM[-DD]]

URLs: Include profile/bio pages. Exclude news/events/press.
Terms: "2024-2027" → start: "2024", end: "2027"
Divisions: Extract exactly from text -- do not infer or make up divisions.
"""
    return prompt