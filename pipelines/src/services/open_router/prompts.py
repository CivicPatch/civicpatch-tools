from datetime import datetime
from typing import List
import shared.utils.config_utils as config_utils

def relevant_page_prompt(page_url: str, jurisdiction_name: str = "", known_roles: List[str] = []):
    jurisdiction_line = f"    Target jurisdiction: {jurisdiction_name}\n" if jurisdiction_name else ""
    known_roles_line = f"    Known elected roles for this municipality: {', '.join(known_roles)}\n" if known_roles else ""
    prompt = f"""
    Your task is to determine if the provided content contains information about the **currently serving main officials**
    of a specific target municipality. Main officials include roles such as Mayor, City Council Members, Aldermen, Select Board Members,
    Commissioners, or other key elected or appointed officials who are part of the **primary governing body** of that municipality.

    Page URL: {page_url}
{jurisdiction_line}{known_roles_line}
    The URL may help you identify which links belong to the municipality's domain(s) when selecting
    relevant_urls. Do NOT use it to determine is_relevant — that must be based solely on page content.
    Do NOT use the page URL's domain to normalize or rewrite any link URLs found in the content.

    ---

    ## Relevant content

    - Structured listings (e.g., tables, lists, or directories) or dedicated sections (e.g., biography, contact, or about pages)
      for the main officials of the municipality.
    - Pages that provide information about the current governing body, such as their names, roles, contact information, or biographies.

    ## Irrelevant content

    - Pages about auxiliary committees, department heads, or other non-elected staff.
      For example: Planning and Zoning Committee, Parks and Recreation Board, Airport Advisory Commission, etc.
      This applies even if primary governing officials (e.g., the Mayor or an Alderman) appear as members
      of that auxiliary body — their membership on the auxiliary board does not make the page relevant.
    - Pages about special districts, utility boards, or other sub-municipal entities (e.g., Water Supply District,
      Fire District, Library Board) — even if they contain a structured roster of named board members.
      These are separate legal entities, not the primary governing body of the municipality.
    ---

    ## Steps for selecting relevant_urls

    `relevant_urls` feeds a web crawler. Always populate it with qualifying links regardless of
    whether `is_relevant` is true or false — the crawler uses these links to discover further
    officials pages even when the current page is already relevant. Evaluate each link primarily
    by its **anchor text and surrounding context** on the page — not by URL structure alone,
    since many municipal CMS platforms use opaque numeric paths (e.g. /179/Township-Board)
    where the slug is the only meaningful signal.

    Return between 3 and 20 URLs. Fewer than 3 suggests over-filtering; more than 20 means you
    are almost certainly including noise — re-evaluate and cut.

    Keep a link only if its anchor text or surrounding context clearly refers to:
    - A governing body or elected role (e.g. "Township Board", "City Council", "Mayor",
      "Board of Trustees", "Aldermen", "Commissioners", "Select Board")
    - A broad government directory or index page (e.g. "Government", "City Hall",
      "Our Government", "Administration") that is likely a hub linking to governance pages
    - A staff or personnel directory that may list elected officials (e.g. "Staff Directory",
      "Directory", "Elected Officials")

    If a link does not clearly match one of the above, discard it.
    Do not include links to municipal services (library, parks, fire, utilities),
    news or announcements, or non-municipal external domains.

    ---

    ## Output Format

    Return a JSON object with the following fields:
    {{
        "relevant_urls": ["https://example.com/council", "https://example.com/directory/departments"],
        "is_relevant": true/false,
    }}

    ---

    ## Critical rules

    - `is_relevant` must be true ONLY if the page's PRIMARY PURPOSE is to present currently
      serving primary governing officials — whether a full roster or a dedicated page for a
      single official. Ask: "Does this page exist to show who currently holds a primary
      governing role?" If the answer is no, set is_relevant to false.
      If `known_roles` are provided and the page is dedicated to a person in one of those
      roles (i.e., the page heading or title names that role), treat it as relevant even if
      a non-voting deputy or assistant also appears on the same page.
      The following are NOT relevant regardless of what names appear in them:
      - News and announcements feeds — even if a post lists newly elected council members by name and ward
      - Meeting minutes, vote records, ordinances, or legislative archives — even if the page is
        titled "City Council" or lives at a city council URL; read the body content, not the title
      - Historical rosters (e.g., "Past Mayors", "Mayor History") — even if the most recent entry is current
      - Auxiliary committee or board pages — even if a Mayor or Alderman sits on the committee
      The test is always the page's purpose, not its content patterns.
    - `relevant_urls` must contain only links whose anchor text clearly signals a governing body,
      elected role, or government directory. Aim for 3–20 URLs; if you exceed 20, you are including noise.
    - Do NOT leave `relevant_urls` empty if your reasoning mentions any URLs — they must appear in the list.
    - `relevant_urls` is for links FOUND ON THIS PAGE pointing elsewhere, not the current page URL itself.
    - Copy URLs exactly as they appear in the content — do NOT normalize, rewrite, or substitute any part of the URL.
    - Do NOT include individual news stories, press releases, or event pages even if they mention an official by name.
    """
    return prompt

# Note: Claude Sonnet 4.6 Generated prompt
def municipality_officials_prompt(known_roles: List[str], state: str = "", county: str | None = None):
    """
    Generate a prompt for extracting municipality officials (Llama-optimized).
    """
    designation_names = config_utils.get_designation_names()
    designations_str = ", ".join(designation_names)
    current_date = datetime.now().strftime("%Y-%m-%d")

    roles_hint_str = ""
    if known_roles:
        roles_hint_str = "- Known elected roles for this municipality: " + ", ".join(known_roles) + "."

    jurisdiction_parts = [f"{county} County" if county else None, state]
    jurisdiction_context = ", ".join(p for p in jurisdiction_parts if p)
    jurisdiction_line = f"\n    Jurisdiction: {jurisdiction_context}" if jurisdiction_context else ""

    return f"""
    You are a data extraction assistant. Extract information about the currently
    serving elected officials of the target municipality from the provided content.

    Current Date: {current_date}{jurisdiction_line}

    STEP 1 - FIND OFFICIALS
    Only extract officials from:
    - A structured table, list, or directory of officials
    - A dedicated biography, about, or contact section for an official
    - A contact or position page for a single elected official, where the page or
      section heading names an elected role and the content includes the person's
      name and their contact information — even if the body primarily describes
      the role's duties rather than the person's biography
    - A page section clearly labeled with a governing body name (e.g. "City Council
      Members", "Board of Aldermen") that lists names as headings or line items —
      even if no contact info, roles, or other details are present; infer the role
      from the section heading
    Do NOT extract officials mentioned only in news articles, event summaries,
    meeting notes, or scattered references.
    Do not extract from content whose primary purpose is to record what officials
    did (votes, minutes, ordinances, resolutions) — even if it is structured and
    includes roles and designations.
    If none of the above valid sources are present in the content, return an empty
    array for "people".
    Do NOT treat a list of links whose text is only a role or position label (e.g.,
    "Mayor", "Councilmember, Place 1", "Alderman") as a structured listing —
    that is a navigation or index section pointing to pages, not a roster of people.
    A valid listing must contain actual person names, not just titles.
    Only extract elected members of the governing body (e.g. Mayor, City Council,
    Board of Aldermen, Board of Commissioners). Exclude everyone else: appointed staff
    and officials from other jurisdictions (county, precinct, special district) even
    when listed alongside governing officials on the same page.
    Treat officials as currently serving unless the content explicitly states
    the roster is historical or past.

    STEP 2 - FOR EACH OFFICIAL, EXTRACT THE FOLLOWING

    name:
    - The person's name only — include all personal name components (honorifics, suffixes, generational markers: Dr., Hon., Jr., Sr., III, etc.) but exclude role or position labels (Mayor, Council Member, City Secretary, etc.).
    - Preserve name punctuation as-is (e.g. a "Last, First" comma is part of the name format, not a separator).
    - Only include an entry if you can see a real person's name. If no name is present, do not add an entry — never invent or infer one. Role or position labels alone (e.g., "Mayor", "Councilmember, Place 1", "Alderman") are not person names, even when they appear as link text; omit them.

    image:
    - The image src value for a profile photo, exactly as it appears in the content.
    - If none found, use null.

    roles:
    - Determine the role using this order:
      1. If the label next to the name is a compound like "Council Member Place 1" or "Council Place 1" —
         strip the trailing position identifier: role="Council Member", designation="Place 1"
      2. If the label is entirely a position identifier ("District 6", "At-Large A", "Ward 3") with no
         role prefix — it is purely a designation. Infer the role from the page title, governing body
         description, or section heading (e.g. "Councilperson").
      3. Otherwise, use the role exactly as written in the source. Do not rename or normalize.
    - Common roles: Mayor, Council Member, Alderman, Commissioner, Select Board Member.
    {roles_hint_str}

    designations:
      Known types: {designations_str}
      Normalize common variations to the canonical type (e.g. "Council Ward 3" → "Ward 3",
      "Posn. 2" → "Position 2", "City-Wide" → "At Large").
      Format as "<canonical type> <value>". If no designation found, use an empty array.
      Do not include role titles as designations.
      A person may have more than one designation — extract all of them.
      Example: "Place 3 (East Ward)" → designations: ["Place 3", "Ward East"]

    phone:
    - A phone number explicitly present in the content.
    - Use in this order: personal number first, then office number, then any
      general municipal contact number found anywhere in the content.
    - If none found, use null.

    email:
    - A valid email address in the format email@domain.tld.
    - Use in this order: personal email first, then office email, then any
      general municipal contact email found anywhere in the content.
    - Contact form URLs (e.g. /email-contact/node/...) are NOT email addresses.
      Treat them as a URL candidate instead.
    - If none found, use null.

    url:
    - Use in this order: official profile page, biography page, contact form URL,
      position listing page, general listing page.
    - Copy the URL exactly as it appears in the content. Do not normalize, lowercase, or remove subdomains like "www".
    - If none found, use null.

    start_date:
    - Date of the most recent election or appointment, if present anywhere in the content.
    - Parse from any written format (e.g. "Jan. 6, 2023", "January 2023", "2023") and normalize.
    - Output format: "YYYY", "YYYY-MM", or "YYYY-MM-DD" depending on precision available.
    - If not present, use null.

    end_date:
    - Date the current term expires, if present anywhere in the content.
    - Parse from any written format and normalize.
    - Output format: "YYYY", "YYYY-MM", or "YYYY-MM-DD" depending on precision available.
    - If not present, use null.

    STEP 3 - ADDITIONAL RULES
    - Only extract information explicitly present in the content. Do not guess or fabricate.
      Exception: inferring a role from a governing body section heading, page title, or description
      is permitted — this is the one case where inference is required rather than direct extraction.
    - One entry per unique person. If the same person appears multiple times, merge into one record.
    - All details must refer to the official's current term.

    STEP 4 - RETURN JSON

    Return a JSON object with exactly this field:
    - people: array of official objects as described above
    """
