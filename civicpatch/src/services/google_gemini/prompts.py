from datetime import datetime
from typing import List
from shared.utils import config_utils
from shared.utils import id_utils
from jobs.people_collector.schemas import ResearchedPerson

def research_municipality_prompt(jurisdiction_ocdid: str, municipality_name: str):
    """
    Generate a prompt for researching municipality information.

    Args:
        jurisdiction_ocdid: Identifier for the municipality.
        municipality_name: Name of the municipality.

    Returns:
        A string containing the prompt.
    """

    jurisdiction_ocdid_parts = id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
    state = jurisdiction_ocdid_parts.state
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
            - designations: List of (ward, district), only if applicable

    3. Create a JSON object with the following structure:
       ```json
       {{
         "government_type": examples - "mayor_council" or "mayor_commission", etc.,
         "people": [
           {{
             "name": "Full name of the official or null if uncertain",
             "roles": ["Mayor", "Council Member", "Commissioner", etc.],
             "designations": ["Ward 1", "District 2", etc.] or [],
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
    designation_names = config_utils.get_designation_names()
    designations_str = ", ".join(designation_names)
    current_date = datetime.now().strftime("%Y-%m-%d")

    maybe_target_people = [person.name for person in people_hint if person.name]

    if maybe_target_people:
        target_text = (
            "If the content includes information about the following people, "
            "they are very likely to be on the council: "
            f"{', '.join(maybe_target_people)}"
        )
    else:
        target_text = ""

    return f"""
    Your task is to extract information about the **current** officials of the target municipality.

    {target_text}

    Only extract people who are currently serving as officials as of {current_date}. 
    Do not include anyone who is described as former, past, resigned, deceased, 
    or otherwise not currently in office.

    Target Roles: {', '.join(roles)}
    Target Designations: {designations_str}
    Current Date: {current_date}

    Return a JSON object in the following format, each having:
    - people: (Array of objects) Each object should have:
      - name: (String) Full name only (no titles)
      - image: (String or null) URL to profile image (https://...)
      - roles: (Array of strings) Active municipal roles
      - designations: (Array of strings) Specific district/ward/etc names
      - phone: (String or null) Formatted phone number
      - email: (String or null) Email address
      - url: (String or null) In order of importance: the official's profile, biography URL, contact form URL, related position listing, or null if none exist.
      - start_date: (String or null) "YYYY" or "YYYY-MM" or "YYYY-MM-DD"
      - end_date: (String or null) "YYYY" or "YYYY-MM" or "YYYY-MM-DD"
    - related_urls: (Array of strings) URLs that potentially contain more information about the officials, ward/district profiles, etc.
    - thoughts: (String) Your reasoning process

    Guidelines:
    - **Only extract information that is explicitly present in the provided content. Do NOT infer or fabricate any details, including email addresses, phone numbers, or URLs.**
    - Roles extraction:
        - Extract roles that match the **target roles** provided (e.g., {', '.join(roles)}).
    - Designation extraction:
        - Extract designations if explicitly mentioned in the text and relevant to the person's role.
        - Examples: "Ward 1", "District 2"
    - Name extraction:
        - Extract full names ONLY, not titles.
    - Phone number extraction:
        - Extract phone numbers even when formatted as Markdown link text.
    - URL extraction:
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
    - Only extract officials if their information appears in a **structured listing** (such as a table, list, or directory) or in a **dedicated biography/about/contact section**.
    - **Do NOT extract officials based on mentions in news articles, event summaries, meeting notes, or scattered references throughout the content.**
    - If the content contains any unstructured mentions of officials (e.g., in news articles, event summaries, or meeting notes), **ignore these mentions entirely** and return an empty array if no structured listing or dedicated section is found.
    - Do NOT infer or guess officials' names, roles, or contact details from context, prior knowledge, or recent mentions. Only extract if the information is presented in a structured way or in a dedicated section.
    - If the content contains a mix of structured listings and unstructured mentions, only extract information from the structured listings or dedicated sections.
    - Ensure all extracted details refer to the **current term** of the official.
    - Use the provided current date ({current_date}) to filter out officials, roles, 
        or terms that are no longer active.
    - Exclude individuals who have resigned, vacated their roles, or are deceased.
    - Ensure only ONE entry exists per unique person's name. Merge all extracted details for the same person into a single record.

    Examples of what NOT to extract:
    - If the content only mentions that an official attended an event, was quoted in a news article, 
      or is referenced in a meeting summary, and there is no structured list or 
      dedicated biography/about/contact section, **return an empty array**.
    """