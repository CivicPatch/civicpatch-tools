from datetime import datetime
import utils.config_utils as config_utils

def municipality_officials_prompt(government_type, content, people_hint):
    """
    Generate a prompt to identify municipality officials from the given content.
    """
    role_configs = config_utils.get_role_configs_by_government_type(government_type)
    roles_list = [role['role'] for role in role_configs]
    roles_str = ", ".join(roles_list)
    division_names = config_utils.get_divisions()
    divisions_str = ", ".join(division_names)

    print("Roles for prompt:", roles_str)
    print("Divisions for prompt:", divisions_str)

    hint_str = ""
    if people_hint:
        hint_names = [person.get("name") for person in people_hint if person.get("name")]
        if hint_names:
            hint_str = "Here are some known officials (may not be a comprehensive list): " + ", ".join(hint_names) + "."

    prompt = f"""
Identify the elected officials and key government employees in the following text.
{hint_str}

The government type is '{government_type}', which typically includes the following roles: {roles_str}.
The divisions are: {divisions_str}.

Provide the results in this JSON format:
Return a JSON object with a key "people" containing an array.
Each object represents one person and MUST include ALL fields
(name, roles, divisions, image, phone_number, email, website, start_date, end_date),
populating with extracted data or null.

Output Field Definitions & Structure:
- name: (String) Full name only (no titles).
- roles: (Array of Objects) Active municipal roles.
         Identify their official job title or specific position.
         This can be a wide variety of municipal roles (e.g., "Mayor", "City Manager", "Selectman",
         "Alderman").
         [{{data: "Mayor", llm_confidence: 0.0-1.0, llm_confidence_reason: "..."}}]
- divisions: (Array of Objects) Specific division/district/ward and name/number,
          only if specified (e.g., "Ward 1", "District 2", "Position 3", "Seat Blue").
          [{{data: "Ward 1", llm_confidence: 0.0-1.0, llm_confidence_reason: "..."}}].
- image: (Object or null) {{data: "https://...", llm_confidence: 0.0-1.0, llm_confidence_reason: "..."}}
- phone_number: (Object or null) {{data: "Formatted Number", llm_confidence: 0.0-1.0, llm_confidence_reason: "..."}}
- email: (Object or null) {{data: "email@example.com", llm_confidence: 0.0-1.0, llm_confidence_reason: "..."}}
- website: (Object or null) {{data: "http(s)://...", llm_confidence: 0.0-1.0, llm_confidence_reason: "..."}}
- start_date: (Object or null) {{data: "YYYY" or "YYYY-MM" or "YYYY-MM-DD", llm_confidence: 0.0-1.0, llm_confidence_reason: "..."}}
- end_date: (Object or null) {{data: "YYYY" or "YYYY-MM" or "YYYY-MM-DD", llm_confidence: 0.0-1.0, llm_confidence_reason: "..."}}

Extraction Instructions:
- Ensure all elected officials and key government employees are extracted.
- Roles extraction:
  - Do not include divisions in the roles field.
- Divisions extraction:
  - Do not infer divisions - only include those explicitly mentioned in the text.

Text: '''{content}'''
"""
    return prompt