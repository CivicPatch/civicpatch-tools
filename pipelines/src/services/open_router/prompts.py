from datetime import datetime
from typing import List

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

    You MUST include every link whose anchor text or surrounding context refers to any of
    the following. These are not candidates to weigh against each other — if a link matches,
    it goes in the list, however many other links the page has and however much navigation
    surrounds it:
    - A governing body or elected role (e.g. "Township Board", "City Council", "Mayor",
      "City Officials", "Board of Trustees", "Aldermen", "Commissioners", "Select Board")
    - A broad government directory or index page (e.g. "Government", "City Hall",
      "Our Government", "Administration") that is likely a hub linking to governance pages
    - A staff or personnel directory that may list elected officials (e.g. "Staff Directory",
      "Directory", "Elected Officials")

    A link that matches one of those and is left out is the single worst outcome here —
    the crawler cannot reach a page it was never told about. If a link does not match any
    of the above, discard it.
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
      If `known_roles` are provided, the page heading or title names one of those roles, and
      the page gives a person's name for it, then `is_relevant` is TRUE. Decide this on the
      heading and that person's details alone — a shared site-wide navigation menu is not
      the page's purpose no matter how much of the content it occupies, and a page whose own
      heading names an elected role is a page about that role, not an index. A non-voting
      deputy or assistant appearing alongside does not change it.
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
def municipality_officials_prompt(
    known_roles: List[str],
    state: str = "",
    county: str | None = None,
    current_date: str | None = None,
):
    """
    Generate a prompt for extracting municipality officials (Llama-optimized).

    `current_date` is an argument because the prompt asks for *currently serving*
    officials: reading the clock in here made the prompt a function of wall-time, so the
    same input produced a different prompt every day and evals silently drifted as terms
    expired. Production leaves it None and gets today; evals pin it.
    """
    current_date = current_date or datetime.now().strftime("%Y-%m-%d")

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
      even if no contact info, titles, or other details are present; take the title
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

    label:
    - Everything the page uses to identify which office this person holds, joined with " - ".
      Collect both parts:
        * the title — what the office is called: "Mayor", "Council Member", "Alderman",
          "Commissioner", "Supervisor", "Clerk"
        * which one — the district, ward, place or number, when a body has several:
          "District 6", "Ward 3", "Place 2", "At-Large A", "Posn. 2"
    - Write each part exactly as the page writes it. Do not rename, expand, abbreviate or
      normalize: "Posn. 2" stays "Posn. 2", "Council Ward 3" stays "Council Ward 3".
    - The two parts are often far apart. The district or place sits beside the name; the
      title is in the section heading, the page title, or the body's description of itself.
      Collect the title from wherever the page states it:
        "Place 3 (East Ward)" under a "City Council" section
            -> "Council Member - Place 3 (East Ward)"
        "District 1" on a page describing "one councilperson per district"
            -> "Councilperson - District 1"
    - If the page states no title anywhere, give the rest alone: "District 6".
    - " - " joins the parts of ONE office, never two. A person holding two offices gets two
      records, one label each:
        "Place 2 (West Ward) and Mayor Pro-Tem: Sharlene Hetzel"
            -> record 1 label: "Council Member - Place 2 (West Ward)"
            -> record 2 label: "Mayor Pro-Tem"
    {roles_hint_str}

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
      Exception: taking a title from a governing body section heading, page title, or description
      is permitted — this is the one case where inference is required rather than direct extraction.
    - One entry per person per label. If the same person appears more than once with the same
      label, merge those into one record; if their labels differ, emit one record per label.
    - All details must refer to the official's current term.

    STEP 4 - RETURN JSON

    Return a JSON object with exactly this field:
    - people: array of official objects as described above
    """


def is_official_jurisdiction_url_prompt() -> str:
    return """
    Determine whether the provided web page content is from the official website of a local government jurisdiction
    (city, township, village, borough, county, etc.).

    Return {"is_official_jurisdiction_url": true} if the page belongs to a real local government entity and contains
    substantive government content — such as elected officials, meeting agendas, services, ordinances, or contact
    information for a governing body.

    Return {"is_official_jurisdiction_url": false} if the page is a parked domain (e.g. "This domain is for sale"),
    a GoDaddy or registrar placeholder, spam, advertisements, or otherwise has no substantive government content.

    IMPORTANT: Return only valid JSON. Do not include any other text.
    """
