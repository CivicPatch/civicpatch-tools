from shared.utils import config_utils
from shared.utils import id_utils


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
    county = jurisdiction_ocdid_parts.county
    designations = config_utils.get_designation_names()
    designations_str = ', '.join(designations)

    location_parts = [municipality_name, f"{county} County" if county else None, state]
    location_str = ", ".join(p for p in location_parts if p)

    return f"""
    Provide the current elected officials for the specified city, including the Mayor (if applicable)
    and other elected members of the local government. Format the response as a JSON object.

    Municipality: {location_str}

    Instructions:

    1. Identify the elected officials in the local government, 
       including the Mayor (if applicable).
       1.1. For each official, extract the following details:
            - name: Full name only (no titles)
            - roles: List of active municipal roles (e.g., Mayor, Council Member)
            - designations: List of ({designations_str}), if applicable

    3. Create a JSON object with the following structure:
       ```json
       {{
         "people": [
           {{
             "name": "Name of the official",
             "roles": ["Mayor", "Council Member", "Commissioner", etc.],
             "designations": ["Ward 1", "District 2", etc.] or [],
           }}
         ]
       }}
       ```

    IMPORTANT: If the response contains anything other than a valid JSON object,
    it will be considered incorrect. Ensure the response is strictly JSON.
    Verify that the response is valid JSON before returning it.
    If it is not valid JSON, retry the generation.
    """
