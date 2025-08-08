from utils.data_utils import MunicipalityContext
import utils.config_utils as config_utils

def research_municipality_prompt(municipality_context: MunicipalityContext):
    """
    Generate a prompt for researching municipality information.

    Args:
        state: State of the municipality.
        municipality_entry: Dictionary containing municipality details (e.g., name, website).

    Returns:
        A string containing the prompt.
    """

    municipality_name = municipality_context["municipality_entry"]["name"]
    state = municipality_context["state"]
    website = municipality_context["municipality_entry"]["website"]
    government_type_keys = "- " + "\n- ".join(list(config_utils.get_government_types().keys()))

    return f"""
    Provide the current elected officials for the specified city, including the Mayor (if applicable) and other elected members of the local government. Format the response as a JSON object.

    Municipality: {municipality_name}, {state}
    Municipality Website (Optional, for context): {website}

    Instructions:

    1. Determine the government type of the city. Available government types:
{government_type_keys}

    2. Identify the total number of elected officials in the local government, including the Mayor (if applicable).

    3. Create a JSON object with the following structure:
       ```json
       {{
         "government_type": examples - "mayor_council" or "mayor_commission", etc.,
         "people": [
           {{
             "name": "Full name of the official or null if uncertain",
             "roles": ["Mayor", "Council Member", "Commissioner", etc.]
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


def municipality_officials_prompt(municipality_context, government_type, content, people, person_name=""):
    """
    Generate a prompt for extracting municipality officials.

    Args:
        municipality_context: Dictionary containing municipality context (e.g., state, government type).
        content: Content to analyze (e.g., markdown text).
        people: List of people hints (e.g., names).
        person_name: Specific person name to focus on (optional).

    Returns:
        A string containing the prompt.
    """
    state = municipality_context["state"]
    municipality_name = municipality_context["municipality_entry"]["name"]

    roles = config_utils.get_roles_for_government_type(government_type)
    division_names = config_utils.get_divisions()
    current_date = municipality_context["current_date"]
    maybe_target_people = [person.get("name") for person in people if person.get("name")]

    target_text = (
        person_name if person_name else
        f"the main governing body of the target municipality. If the content includes information about the following people, they are very likely to be on the council: {', '.join(maybe_target_people)}"
        if maybe_target_people else
        "the main governing body of the target municipality."
    )

    return f"""
    First, determine if the content contains relevant information about {target_text}.
    If not, return an empty JSON array `[]`.

    Target Municipality: {municipality_name}, {state}
    Target Roles: {', '.join(roles)}
    Target Divisions: {', '.join(division_names)}
    Current Date: {current_date}

    Return a JSON object with people, each having:
    - name: Full name only (not titles)
    - phone_number: {{data, llm_confidence, llm_confidence_reason}}
    - email: {{data, llm_confidence, llm_confidence_reason}}
    - website: {{data, llm_confidence, llm_confidence_reason}}
    - roles: [{{data, llm_confidence, llm_confidence_reason}}]
    - divisions: [{{data, llm_confidence, llm_confidence_reason}}]
    - start_date: {{data, llm_confidence, llm_confidence_reason}}
    - end_date: {{data, llm_confidence, llm_confidence_reason}}

    The JSON object should have the following structure:
    {{
      "people": [],
      "thought": "Your reasoning or thought process behind the extraction" // Restrict to 1 sentence.
    }}

    Guidelines:
    - For "llm_confidence": Use 0-1 scale with reason for your confidence.
    - Roles extraction:
        - Extract roles that match the **target roles** provided (e.g., {', '.join(roles)}).
    - Division extraction:
        - Extract divisions if explicitly mentioned in the text and relevant to the person's role.
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

    Here is the content (in markdown):
    {content}
    """