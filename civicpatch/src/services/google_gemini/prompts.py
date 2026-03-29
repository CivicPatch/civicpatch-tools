from datetime import datetime
from typing import List
from shared.utils import config_utils
from shared.utils import id_utils
from jobs.people_collector.schemas import ResearchedPerson


def relevant_page_prompt(page_url: str):
    return f"""
    Your task is to determine if the provided content contains information about the **currently serving main officials**
    of the target municipality. Main officials include roles such as Mayor, City Council Members, Aldermen, Select Board Members,
    Commissioners, or other key elected or appointed officials who are part of the **primary governing body** of the municipality.

    Page URL: {page_url}
    The URL may help you identify which links belong to the municipality's domain(s) when selecting
    relevant_urls. Do NOT use it to determine is_relevant — that must be based solely on page content.
    Do NOT use the page URL's domain to normalize or rewrite any link URLs found in the content.

    **Relevant content includes:**
    - Structured listings (e.g., tables, lists, or directories) or dedicated sections (e.g., biography, contact, or about pages)
      for the main officials of the municipality.
    - Pages that provide information about the current governing body, such as their names, roles, contact information, or biographies.

    **Irrelevant content includes:**
    - Pages that only mention auxiliary committees, department heads, supervisors, or other non-elected officials.
      For example: Planning and Zoning Committee, Parks and Recreation Board, etc.
    - Pages about the City Manager's or City Administrator's office. The City Manager is an appointed
      administrator who serves at the discretion of the governing body — they are NOT a member of the
      primary governing body (Mayor, Council, etc.) and their page must be marked is_relevant: false.

    **Steps for selecting relevant_urls:**
    1. Extract ALL links found anywhere on the page into a complete list.
    2. For each link, ask: "If I followed this link, would I likely land on a page that lists or describes
       the primary governing body (mayor, council members, commissioners, etc.) or provides a directory
       of municipal departments and staff?"
       Keep the link if the answer is yes.
    3. Prefer section-level or landing pages over individual content items. Ask: "Does this link point to
       a navigational index or overview page, or to a single specific article, event, or news item?"
       - Keep: any link whose anchor text or URL refers to government, officials, council, board members,
         aldermen, commissioners, mayor, or municipal staff and directories
         (e.g. /Government, /Council, /CityOfficials, /Directory/Departments)
       - Keep: individual pages explicitly for the Mayor (e.g., /Mayor/Bio, /About-the-Mayor, /Our-Mayor) —
         the mayor is a primary official, so their dedicated page is always relevant
       - Discard: individual news stories, press releases, or event pages about a specific item —
         even if they mention an official's name in the title or URL
    4. Return the filtered list as relevant_urls.

    **Output Format:**
    Return a JSON object with the following fields:
    {{
        "relevant_urls": ["https://example.com/council", "https://example.com/directory/departments"],
        "is_relevant": true/false,
    }}

    **Critical rules:**
    - `is_relevant` must be true ONLY if the page is *about* currently serving primary governing
      officials — e.g., a council roster, a staff directory, or a bio/profile page for an official.
      Names appearing incidentally inside news items, legal notices, tax notices, meeting minutes,
      vote records, or ordinances do NOT make a page relevant — set is_relevant to false.
      Pages that list officials in historical or chronological order (e.g., "Mayor History",
      "Past Mayors", "Former Council Members") are NOT relevant — even if the most recent
      entry is a currently serving official. The page's purpose is what matters, not whether
      a current name appears in it.
      A city council landing page whose content is ordinances and vote rolls (e.g.
      "UPON CALLING FOR A VOTE ... Gary Chumley, Mayor — Does not Vote; Aaron Smith — Aye")
      is NOT relevant — it is a legislative archive, not a roster.
    - `relevant_urls` must include ANY navigation or directory link on the page that could lead to
      the primary governing body — including department directories, staff listings, and government
      section pages — even if the current page itself is not relevant.
    - Do NOT leave `relevant_urls` empty if your reasoning mentions any URLs — they must appear in the list.
    - `relevant_urls` is for links FOUND ON THIS PAGE pointing elsewhere, not the current page URL itself.
    - Copy URLs exactly as they appear in the content — do NOT normalize, rewrite, or substitute any part of the URL.
    - Do NOT include individual news stories, press releases, or event pages even if they mention an official by name.
    - Only include URLs hosted on the municipality's own domain(s) (e.g. city, county, town websites).
      Do NOT include URLs from third-party external domains, even if civic-related. Examples to exclude:
      social media (facebook.com, twitter.com, instagram.com, linkedin.com, youtube.com),
      third-party agenda/meeting platforms (civicclerk.com, civicplus.com, granicus.com),
      third-party code/ordinance sites (municode.com, library.municode.com),
      third-party reporting tools (seeclickfix.com), or any other non-municipal domain.
    """


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
    - A page section clearly labeled with a governing body name (e.g. "City Council
      Members", "Board of Aldermen") that lists names as headings or line items —
      even if no contact info, roles, or other details are present

    Treat officials as currently serving unless the content explicitly states
    the roster is historical or past.

    If only unstructured mentions exist (news articles, event summaries, meeting
    notes, scattered references), return an empty array for "people".

    If structured and unstructured content are mixed, extract only from the
    structured portion.

    Do NOT extract office staff, aides, assistants, schedulers, constituent services
    representatives, chiefs of staff, or other administrative employees who work for
    an elected official — only extract elected or appointed members of the primary
    governing body (Mayor, Council Members, Commissioners, etc.).

    Examples of valid sources to extract from:
    - A table listing council members with their names, roles, and contact info
    - A dedicated "Meet Your Council" page with individual bios
    - A section headed "City Council Members" listing names as headings with no
      other details — infer the role from the section heading

    Examples of sources to ignore:
    - A staff directory for a council member's office (lists aides, not officials)
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
      **Strip any trailing position identifier (Place N, Ward N, District N, At-Large, etc.)
      from the role — it belongs in "designations".**
      Example: "Council Place 1" or "Council Member Place 1" → role="Council Member", designation="Place 1"
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