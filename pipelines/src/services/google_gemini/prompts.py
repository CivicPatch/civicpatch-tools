from datetime import datetime
from typing import List
from shared.utils import config_utils
from shared.utils import id_utils
from jobs.people_collector.schemas import ResearchedPerson


def relevant_page_prompt(page_url: str, jurisdiction_name: str = ""):
    jurisdiction_line = f"    Target jurisdiction: {jurisdiction_name}\n" if jurisdiction_name else ""
    return f"""
    Your task is to determine if the provided content contains information about the **currently serving main officials**
    of a specific target municipality. Main officials include roles such as Mayor, City Council Members, Aldermen, Select Board Members,
    Commissioners, or other key elected or appointed officials who are part of the **primary governing body** of that municipality.

    Page URL: {page_url}
{jurisdiction_line}
    The URL may help you identify which links belong to the municipality's domain(s) when selecting
    relevant_urls. Do NOT use it to determine is_relevant — that must be based solely on page content.
    Do NOT use the page URL's domain to normalize or rewrite any link URLs found in the content.

    **Relevant content includes:**
    - Structured listings (e.g., tables, lists, or directories) or dedicated sections (e.g., biography, contact, or about pages)
      for the main officials of the municipality.
    - Pages that provide information about the current governing body, such as their names, roles, contact information, or biographies.

    **Irrelevant content includes:**
    - Pages about auxiliary committees, department heads, supervisors, or other non-elected officials.
      For example: Planning and Zoning Committee, Parks and Recreation Board, Airport Advisory Commission, etc.
      This applies even if primary governing officials (e.g., the Mayor or an Alderman) appear as members
      of that auxiliary body — their membership on the auxiliary board does not make the page relevant.
    - Pages about special districts, utility boards, or other sub-municipal entities (e.g., Water Supply
      District, Fire District, Library Board) — even if they contain a structured roster of named members.
      These are separate legal entities, not the primary governing body of the municipality.
    - Pages about the City Manager's or City Administrator's office. The City Manager is an appointed
      administrator who serves at the discretion of the governing body — they are NOT a member of the
      primary governing body (Mayor, Council, etc.) and their page must be marked is_relevant: false.

    **Steps for selecting relevant_urls:**
    `relevant_urls` feeds a web crawler whose goal is to eventually reach a page listing the primary
    governing officials. Think of each URL as a breadcrumb: keep it if it could plausibly be one or
    more hops away from an officials roster — even if it is not directly about officials itself.
    Err heavily on the side of keeping. A false positive costs one extra scrape; a false negative
    means the crawler never finds the officials.

    1. Extract ALL links found anywhere on the page into a complete list.
    2. Keep a link if it could be on the path to an officials roster. This includes:
       - Any broad navigational or directory page, even if it does not explicitly mention officials
         (e.g. /Departments, /Government, /City-Hall, /About, /Our-City, /Services)
       - Pages that name a governing body or official role
         (e.g. /Council, /Mayor, /Aldermen, /Commissioners, /Board-Members)
       - Staff or personnel directories that may list elected officials among other staff
       - Individual pages dedicated to the Mayor or other primary officials
    3. Discard only obvious dead ends:
       - Individual news stories, press releases, blog posts, or event pages
       - Non-municipal external domains
       - File downloads (PDFs, DOCs) that are a single document rather than a navigable page

    **Output Format:**
    Return a JSON object with the following fields:
    {{
        "relevant_urls": ["https://example.com/council", "https://example.com/directory/departments"],
        "is_relevant": true/false,
    }}

    **Critical rules:**
    - `is_relevant` must be true ONLY if the page's PRIMARY PURPOSE is to present currently
      serving primary governing officials. Ask: "Does this page exist to show who is on the
      governing body right now?" If the answer is no, set is_relevant to false.
      The following are NOT relevant regardless of what names appear in them:
      - News and announcements feeds — even if a post lists newly elected council members by name and ward
      - Meeting minutes, vote records, ordinances, or legislative archives — even if the page is
        titled "City Council" or lives at a city council URL; read the body content, not the title
      - Historical rosters (e.g., "Past Mayors", "Mayor History") — even if the most recent entry is current
      - Auxiliary committee or board pages — even if a Mayor or Alderman sits on the committee
      The test is always the page's purpose, not its content patterns.
    - `relevant_urls` is a crawl frontier, not a relevance filter. Include any link that could be
      one or more hops from an officials roster. When in doubt, keep it.
    - Do NOT leave `relevant_urls` empty if your reasoning mentions any URLs — they must appear in the list.
    - `relevant_urls` is for links FOUND ON THIS PAGE pointing elsewhere, not the current page URL itself.
    - Copy URLs exactly as they appear in the content — do NOT normalize, rewrite, or substitute any part of the URL.
    - Do NOT include individual news stories, press releases, or event pages even if they mention an official by name.
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
    Only extract from content whose primary purpose is to present who currently
    holds office. Do not extract from content whose primary purpose is to record
    what officials did — even if it is structured and includes roles and designations.

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
      Only include an entry if a real person's name is present. If the position appears vacant, unfilled, or the only available name is a placeholder or role description (e.g., "Councilmember Place 6 Name", "Council Member 2 Name"), omit the entry entirely.

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