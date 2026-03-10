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
    designations = config_utils.get_designation_names()
    designations_str = ', '.join(designations)

    return f"""
    Provide the current elected officials for the specified city, including the Mayor (if applicable) 
    and other elected members of the local government. Format the response as a JSON object.

    Municipality: {municipality_name}, {state}

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
             "name": "Full name of the official or "Vacant Vacant" if uncertain",
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

# Note: Claude Sonnet 4.6 Generated prompt
def municipality_officials_prompt(_people_hint: List[ResearchedPerson]):
    """
    Generate a prompt for extracting municipality officials (Gemini Flash optimized).
    """
    designation_names = config_utils.get_designation_names()
    designations_str = ", ".join(designation_names)
    current_date = datetime.now().strftime("%Y-%m-%d")

    return f"""
    You are a precise government data extraction assistant specializing in 
    municipal records and official rosters.

    ## Task

    Extract information about the currently serving elected officials of the
    target municipality from the provided content.

    Current Date: {current_date}

    ---

    ## Scope

    Only extract officials whose information appears in:
    - A structured table, list, or directory of officials
    - A dedicated biography, about, or contact section for an official

    Treat officials as currently serving unless the content explicitly states
    the roster is historical or past.

    If only unstructured mentions exist (news articles, event summaries, meeting
    notes, scattered references), return an empty array for "people".

    If structured and unstructured content are mixed, extract only from the
    structured portion.

    Examples of valid sources to extract from:
    - A table listing council members with their names, roles, and contact info
    - A dedicated "Meet Your Council" page with individual bios
    - A staff directory with names, titles, and phone numbers

    Examples of sources to ignore:
    - "Mayor Johnson attended the ribbon cutting ceremony last Tuesday"
    - "The council voted 4-1 in favor, with Alderman Smith dissenting"

    ---

    ## Fields

    - **name** (String or null)
      Full name only, no titles or honorifics.
      If the position is vacant, use "Vacant Vacant".

    - **image** (String or null)
      URL to a profile image (must start with https://).

    - **roles** (Array of strings)
      Active municipal role(s) exactly as written in the source. Do not rename,
      normalize, or substitute role titles.
      Roles you may encounter include: Mayor, Council Member, Alderman,
      Commissioner, Select Board Member — but always use the source's exact wording.
      If the listing does not explicitly state a role but the surrounding content 
      clearly identifies the group (e.g. "The City Council is comprised of a Mayor 
      and 4 Council Members"), use that contextual role for all members in the listing.
      **If the value matches a known designation type ({designations_str}), 
      it belongs in "designations", not here.**

    - **designations** (Array of strings)
      Ward, district, seat, or similar identifiers associated with the official.
      Known designation types: {designations_str}
      Normalize variations to the canonical type (e.g. "Council Ward 3" → "Ward 3", "City-Wide" → "At Large").
      Format as "<canonical type> <value>". "At Large" has no value — output exactly "At Large".
      Do NOT put role titles (Mayor, Council Member, etc.) here — those belong in "roles".
      If none found, use an empty array.

    - **phone** (String or null)
      A phone number explicitly present in the content.
      Priority: personal > office > general municipal contact number found
      anywhere in the content as a last resort fallback.

    - **email** (String or null)
      A valid email address in the format email@domain.tld.
      Priority: personal > office > general municipal contact email found
      anywhere in the content as a last resort fallback.
      Contact form URLs are NOT valid emails — treat them as a URL candidate instead.

    - **url** (String or null)
      Priority: official profile > biography > contact form URL > position
      listing > general listing.

    - **start_date** (String or null)
      Date of most recent election or appointment, if explicitly stated.
      Format: "YYYY", "YYYY-MM", or "YYYY-MM-DD".
      Example: "Elected November 2020, reelected November 2024" → "2024-11".

    - **end_date** (String or null)
      Date current term expires, if explicitly stated.
      Format: "YYYY", "YYYY-MM", or "YYYY-MM-DD".
      Example: "Term ends December 2028" → "2028-12".

    - **relevant_urls** (Array of strings)
      URLs explicitly present in the content that may lead to further information
      about officials, such as biography pages, ward profiles, or council subpages.

    ---

    ## Rules

    - Only extract information explicitly present in the content.
      Do not infer, guess, or fabricate any details.
      Exception: general contact emails or phone numbers explicitly present
      anywhere in the content may be used as a fallback for individuals
      with no personal or office contact info.
    - One entry per unique person. Merge all details for the same person into
      a single record.
    - All extracted details must refer to the official's current term.
    """