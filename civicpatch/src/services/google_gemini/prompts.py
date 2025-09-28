from datetime import datetime
from typing import List
from utils import id_utils, config_utils
from schemas import ResearchedPerson

def research_municipality_prompt(jurisdiction_id: str, municipality_name: str):
    """
    Generate a prompt for researching municipality information.

    Args:
        jurisdiction_id: Identifier for the municipality.
        municipality_name: Name of the municipality.

    Returns:
        A string containing the prompt.
    """

    jurisdiction_id_parts = id_utils.parse_jurisdiction_id(jurisdiction_id)
    state = jurisdiction_id_parts.state
    government_type_keys = "- " + "\n- ".join(list(config_utils.get_government_types().keys()))

    return f"""
    Provide the current elected officials for the specified city, including the Mayor (if applicable) and other elected members of the local government. Format the response as a JSON object.

    Municipality: {municipality_name}, {state}

    Instructions:

    1. Determine the government type of the city. Available government types:
{government_type_keys}

    2. Identify the elected officials in the local government, 
       including the Mayor (if applicable).
       2.1. For each official, extract the following details:
            - name: Full name only (no titles)
            - roles: List of active municipal roles (e.g., Mayor, Council Member)
            - divisions: List of (ward, district), only if applicable

    3. Create a JSON object with the following structure:
       ```json
       {{
         "government_type": examples - "mayor_council" or "mayor_commission", etc.,
         "people": [
           {{
             "name": "Full name of the official or null if uncertain",
             "roles": ["Mayor", "Council Member", "Commissioner", etc.],
             "divisions": ["Ward 1", "District 2", etc.] or [],
           }}
         ],
         "notes": "Brief notes about the search and results"
       }}
       ```

    IMPORTANT: If the response contains anything other than a valid JSON object,
    it will be considered incorrect. Ensure the response is strictly JSON.
    Verify that the response is valid JSON before returning it.
    If it is not valid JSON, retry the generation.
    """


def municipality_officials_prompt(government_type: str, people_hint: List[ResearchedPerson]):
    """
    Generate a prompt for extracting municipality officials.
    """
    roles = config_utils.get_roles_by_government_type(government_type)
    division_names = config_utils.get_divisions()
    current_date = datetime.now().strftime("%Y-%m-%d")

    person_name = None
    maybe_target_people = [person.name for person in people_hint if person.name]

    if len(maybe_target_people) == 1:
        person_name = maybe_target_people[0]

    if person_name:
        target_text = person_name
    elif maybe_target_people:
        target_text = (
            "the main governing body of the target municipality. "
            "If the content includes information about the following people, "
            "they are very likely to be on the council: "
            f"{', '.join(maybe_target_people)}"
        )
    else:
        target_text = "the main governing body of the target municipality."

    return f"""
    First, determine if the content contains relevant information about {target_text}.
    If not, return an empty JSON array `[]`.

    Target Roles: {', '.join(roles)}
    Target Divisions: ward, district
    Current Date: {current_date}

    Return a JSON object with people, each having:
    - name: (String) Full name only (no titles)
    - image: (String or null) URL to profile image (https://...)
    - roles: (Array of strings) Active municipal roles
    - divisions: (Array of strings) Specific district/ward names
    - phone_number: (String or null) Formatted phone number
    - email: (String or null) Email address
    - website: (String or null) Use the official's profile or biography URL if available; otherwise, use a contact form URL. If neither exists, set to null.
    - start_date: (String or null) "YYYY" or "YYYY-MM" or "YYYY-MM-DD"
    - end_date: (String or null) "YYYY" or "YYYY-MM" or "YYYY-MM-DD"

    Guidelines:
    - Roles extraction:
        - Extract roles that match the **target roles** provided (e.g., {', '.join(roles)}).
    - Division extraction:
        - Extract divisions if explicitly mentioned in the text and relevant to the person's role.
        - Examples: "Ward 1", "District 2"
    - Name extraction:
        - Extract full names ONLY, not titles.
    - Phone number extraction:
        - Extract phone numbers even when formatted as Markdown link text.
    - Website extraction:
        - Extract URLs starting with "http://" or "https://".
    - Email extraction:
        - Extract email addresses found directly in the text or formatted as Markdown link text.
    - Start and End Date Extraction:
        - Extract dates only if explicitly written in the text.
        - **Start Date**:
            - Extract the date associated with the **most recent election or appointment**.
            - Ignore past terms or historical dates unless explicitly stated as the current term.
            - Example: "Elected in November 2020 and reelected in November 2024" → `start_date`: `2024-11`.
        - **End Date**:
            - Extract the date associated with the **current term expiration**.
            - Example: "Term ends December 2028" → `end_date`: `2028-12`.
        - If no explicit dates are found, set both `start_date` and `end_date` to `null`.

    Additional Rules:
    - Ensure all extracted details refer to the **current term** of the official.
    - Use the provided `current_date` to filter out roles or terms that are no longer active.
    - Exclude individuals who have resigned, vacated their roles, or are deceased.
    - Ensure only ONE entry exists per unique person's name. Merge all extracted details for the same person into a single record.
    """