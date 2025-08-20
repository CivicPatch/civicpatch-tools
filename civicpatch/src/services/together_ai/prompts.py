from datetime import datetime
import utils.config_utils as config_utils

def municipality_officials_prompt(government_type, people_hint):
    """
    Generate a prompt to identify municipality officials from the given content.
    """
    # role_configs = config_utils.get_role_configs_by_government_type(government_type)
    # roles_list = [role['role'] for role_configs]
    # roles_str = ", ".join(roles_list)
    division_names = config_utils.get_divisions()
    divisions_str = ", ".join(division_names)

    hint_str = ""
    if people_hint:
        hint_names = [person.get("name") for person in people_hint if person.get("name")]
        if hint_names:
            hint_str = "Here are the list of known target people (may be missing or include a few extra): " + ", ".join(hint_names) + "."

    prompt = f"""
Identify elected municipal officials in the following markdown text.
{hint_str}

The government type is '{government_type}'.
The divisions are: {divisions_str}.

Provide the results in this JSON format:
Return a JSON object with a key "people" containing an array of every person found in the text.
Each object represents one person and should include the following fields:
(name, roles, divisions, image, phone_number, email, website, start_date, end_date),
populating with extracted data or null.

Output Field Definitions & Structure:
- name: (String) Full name only (no titles).
- roles: (Array of strings) Active municipal roles.
         Identify their official job title or specific position.
         (Ex: "Mayor", "City Council Member")
- divisions: (Array of strings) Specific division/district/ward and name/number,
          only if specified (e.g., "Ward 1", "District 2", "Position 3", "Seat Blue").
- image: (String or null) Direct URL to profile photo/headshot image file.
        Must end in image extension (.jpg, .jpeg, .png, etc)
        Example: "https://example.com/photos/person.jpg"
- phone_number: (String or null) Phone number.
- email: (String or null) Email address (email@example.com)
- website: (String or null) URL to the person's profile/bio page.
          Example: "https://example.com/council/members/person"
          Do not include image URLs here.
- start_date: (String or null) Start date of current term in "YYYY" or "YYYY-MM" or "YYYY-MM-DD" format. 
              For a term like "2024-2027", use "2024" as start_date.
- end_date: (String or null) End date of current term in "YYYY" or "YYYY-MM" or "YYYY-MM-DD" format.
           For a term like "2024-2027", use "2027" as end_date.

Extraction Instructions:
- Ensure all elected officials and key government employees are extracted.
- Roles extraction:
  - Do not include divisions in the roles field.
- Divisions extraction:
  - Do not infer divisions - only include those explicitly mentioned in the text.
- Date extraction
  - For term ranges (e.g., "2024-2027"):
    - Extract the first year as start_date ("2024")
    - Extract the second year as end_date ("2027")
  - Only include dates in YYYY, YYYY-MM, or YYYY-MM-DD format
  - Do not include ranges in either field
"""
    return prompt