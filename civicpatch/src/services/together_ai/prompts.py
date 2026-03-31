from datetime import datetime
from typing import List
import shared.utils.config_utils as config_utils

def relevant_page_prompt(page_url: str, jurisdiction_name: str = ""):
    jurisdiction_line = f"    Target jurisdiction: {jurisdiction_name}\n" if jurisdiction_name else ""
    prompt = f"""
    Your task is to determine if the provided content contains information about the **currently serving main officials**
    of a specific target municipality. Main officials include roles such as Mayor, City Council Members, Aldermen, Select Board Members,
    Commissioners, or other key elected or appointed officials who are part of the **primary governing body** of that municipality.

    Page URL: {page_url}
{jurisdiction_line}
    The URL may help you identify which links belong to the municipality's domain(s) when selecting
    relevant_urls. Do NOT use it to determine is_relevant — that must be based solely on page content.
    Do NOT use the page URL's domain to normalize or rewrite any link URLs found in the content.

    ---

    ## Relevant content

    - Structured listings (e.g., tables, lists, or directories) or dedicated sections (e.g., biography, contact, or about pages)
      for the main officials of the municipality.
    - Pages that provide information about the current governing body, such as their names, roles, contact information, or biographies.

    ## Irrelevant content

    - Pages about auxiliary committees, department heads, supervisors, or other non-elected officials.
      For example: Planning and Zoning Committee, Parks and Recreation Board, Airport Advisory Commission, etc.
      This applies even if primary governing officials (e.g., the Mayor or an Alderman) appear as members
      of that auxiliary body — their membership on the auxiliary board does not make the page relevant.
    - Pages about special districts, utility boards, or other sub-municipal entities (e.g., Water Supply District,
      Fire District, Library Board) — even if they contain a structured roster of named board members.
      These are separate legal entities, not the primary governing body of the municipality.
    - Pages about the City Manager's or City Administrator's office. The City Manager is an appointed
      administrator who serves at the discretion of the governing body — they are NOT a member of the
      primary governing body (Mayor, Council, etc.) and their page must be marked is_relevant: false.

    ---

    ## Steps for selecting relevant_urls

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
    return prompt

# Note: Claude Sonnet 4.6 Generated prompt
def municipality_officials_prompt(roles_hint: List[str]):
    """
    Generate a prompt for extracting municipality officials (Llama-optimized).
    """
    designation_names = config_utils.get_designation_names()
    designations_str = ", ".join(designation_names)
    current_date = datetime.now().strftime("%Y-%m-%d")

    roles_hint_str = ""
    if roles_hint:
        roles_hint_str = "- An example of roles relevant to this municipality: " + ", ".join(roles_hint) + "."

    return f"""
    You are a data extraction assistant. Extract information about the currently 
    serving elected officials of the target municipality from the provided content.

    Current Date: {current_date}

    STEP 1 - FIND OFFICIALS
    Only extract officials from:
    - A structured table, list, or directory of officials
    - A dedicated biography, about, or contact section for an official
    - A page section clearly labeled with a governing body name (e.g. "City Council
      Members", "Board of Aldermen") that lists names as headings or line items —
      even if no contact info, roles, or other details are present; infer the role
      from the section heading
    Do NOT extract officials mentioned only in news articles, event summaries,
    meeting notes, or scattered references. If no structured listing exists,
    return an empty array for "people".
    Only extract from content whose primary purpose is to present who currently
    holds office. Do not extract from content whose primary purpose is to record
    what officials did — even if it is structured and includes roles and designations.
    Do NOT treat a list of links whose text is only a role or position label (e.g.,
    "Mayor", "Councilmember, Place 1", "Alderman") as a structured listing —
    that is a navigation or index section pointing to pages, not a roster of people.
    A valid listing must contain actual person names, not just titles.
    Do NOT extract office staff, aides, assistants, schedulers, constituent services
    representatives, chiefs of staff, or other administrative employees who work for
    an elected official — only extract elected or appointed members of the primary
    governing body (Mayor, Council Members, Commissioners, etc.).
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
    - The official's role exactly as written in the source. Do not rename or normalize.
    - Common roles you may encounter: Mayor, Council Member, Alderman, Commissioner,
      Select Board Member. Always use the source's exact wording.
    - Strip any trailing position identifier (Place N, Ward N, District N, At-Large, etc.) from the role — it belongs in designations.
      Example: "Council Place 1" or "Council Member Place 1" → role="Council Member", designation="Place 1"
    {roles_hint_str}

    designations:
      Known types: {designations_str}
      Normalize common variations to the canonical type (e.g. "Council Ward 3" → "Ward 3", 
      "Posn. 2" → "Position 2", "City-Wide" → "At Large").
      Format as "<canonical type> <value>". If no designation found, use an empty array.
      Do not include role titles as designations.      

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
    - Date of the most recent election or appointment, if explicitly stated.
    - Format: "YYYY", "YYYY-MM", or "YYYY-MM-DD".
    - If not explicitly stated, use null.

    end_date:
    - Date the current term expires, if explicitly stated.
    - Format: "YYYY", "YYYY-MM", or "YYYY-MM-DD".
    - If not explicitly stated, use null.

    STEP 3 - ADDITIONAL RULES
    - Only extract information explicitly present in the content. Do not guess or fabricate.
    - One entry per unique person. If the same person appears multiple times, merge into one record.
    - All details must refer to the official's current term.

    STEP 4 - RETURN JSON

    Return a JSON object with exactly this field:
    - people: array of official objects as described above
    """