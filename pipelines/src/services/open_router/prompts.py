from datetime import datetime
from typing import List

from pydantic import BaseModel


def relevant_page_prompt(
    page_url: str,
    jurisdiction_name: str = "",
    known_roles: List[str] = [],
    # The bodies cp.org already holds for this jurisdiction, by name. Without them the rules
    # below rule out an Office of the Mayor page as a department: Jackson TN's lives at
    # `/government/mayorsoffice`, a sibling of `/government/departments/*`, and reads exactly
    # like the auxiliary pages the Irrelevant section is written to reject.
    known_organizations: List[str] = [],
):
    jurisdiction_line = (
        f"    Target jurisdiction: {jurisdiction_name}\n" if jurisdiction_name else ""
    )
    known_roles_line = (
        f"    Known elected roles for this municipality: {', '.join(known_roles)}\n"
        if known_roles
        else ""
    )
    known_organizations_line = (
        f"    Governing bodies of this municipality: {', '.join(known_organizations)}\n"
        if known_organizations
        else ""
    )
    # Both halves or neither. Unconditional, the rule read as a general softening of the
    # Irrelevant section on every page with no bodies listed — which is every cold-start page and
    # every eval case predating the list — and it cost cases on the first `evalsr` run after it
    # was added.
    # Both halves or neither. Unconditional, the rule read as a general softening of the
    # Irrelevant section on every page with no bodies listed — which is every cold-start page and
    # every eval case predating the list — and it cost cases on the first `evalsr` run after it
    # was added.
    known_organizations_rule = (
        """
    - A page about a body named under "Governing bodies of this municipality" above, whatever its
      URL or site section suggests. An Office of the Mayor page filed beside the departments is
      still the mayor's office."""
        if known_organizations
        else ""
    )
    prompt = f"""
    Decide two things about the page content provided: whether it presents the **currently
    serving main officials** of the target municipality, and which of its links a crawler should
    follow to find more of them.

    Main officials are the Mayor, City Council Members, Aldermen, Select Board Members,
    Commissioners and others who make up the municipality's **primary governing body**.

    Page URL: {page_url}
{jurisdiction_line}{known_roles_line}{known_organizations_line}
    The URL tells you which links share the municipality's domain. It tells you nothing about
    `is_relevant`, which comes from the page content alone.

    ---

    ## is_relevant

    True when the page exists to show who currently holds a primary governing role: a roster, a
    directory, or one official's own page. Ask "does this page exist to show who holds office
    right now?" and answer on the page's own heading and body.

    Also true, and these are the ones most often got wrong:
    - The heading names a known elected role and the page gives a person's name for it. A
      site-wide navigation menu is not the page's purpose however much of the content it fills,
      and a non-voting deputy appearing alongside does not change the answer.
    - The page lists the municipality's own officials and also lists appointed staff. A small
      town's "City Officials" page naming the Mayor and council members alongside the City
      Manager, Water Supervisor and Fire Chief is the roster. Judge it by whether the governing
      body's members are presented as such, not by who else shares the page.{known_organizations_rule}

    When a page names a person who holds one of the roles above and you cannot tell whether it is
    a roster or a department landing page, answer true. The two mistakes do not cost the same: a
    page wrongly called relevant costs one extraction that returns nobody, while a page wrongly
    called irrelevant is never read again and its officials are never found.

    False for these, whoever is named in them:
    - Auxiliary committees, boards and commissions (Planning and Zoning, Parks and Recreation,
      Airport Advisory), and pages about department heads or other non-elected staff. A Mayor or
      Alderman sitting on such a body does not make its page relevant.
    - Special districts, utility boards and other sub-municipal entities (Water Supply District,
      Fire District, Library Board), which are separate legal entities. A structured roster of
      their board members is still not this municipality's governing body.
    - News, announcements and press releases, even a post naming newly elected members by ward.
    - Meeting minutes, vote records, ordinances and legislative archives, even titled "City
      Council" or living at a city council URL. Read the body, not the title.
    - Historical rosters ("Past Mayors", "Mayor History"), even where the most recent entry is
      the current holder.

    ---

    ## relevant_urls

    These feed the crawler, so populate them whether or not the page itself is relevant: a page
    already listing officials still links to more of them. Judge each link by its **anchor text
    and surrounding context**, not by URL structure, since municipal CMS platforms use opaque
    numeric paths (e.g. /179/Township-Board) where the slug is the only signal.

    Include every link whose anchor text or context refers to:
    - a governing body or elected role ("Township Board", "City Council", "Mayor", "City
      Officials", "Board of Trustees", "Aldermen", "Commissioners", "Select Board")
    - a government directory or index page likely to link onward to governance pages
      ("Government", "City Hall", "Our Government", "Administration")
    - a staff or personnel directory that may list elected officials ("Staff Directory",
      "Directory", "Elected Officials")

    These are not candidates to weigh against each other. A qualifying link left out is the worst
    outcome here, because the crawler cannot reach a page it was never told about — include every
    one, however few qualify and however much navigation surrounds them. A small site's menu may
    offer exactly one, and returning nothing because one felt too few is the failure to avoid.
    Stop at 20; beyond that you are including noise.

    Leave out municipal services (library, parks, fire, utilities), individual news stories,
    press releases and event pages, and non-municipal external domains. Copy each URL exactly as
    it appears in the content, without normalizing or rewriting any part of it, and do not
    include the current page's own URL.

    ---

    ## Output Format

    Return a JSON object with the following fields:
    {{
        "relevant_urls": ["https://example.com/council", "https://example.com/directory/departments"],
        "is_relevant": true/false,
    }}
    """
    return prompt


class PromptOrganization(BaseModel):
    """A body as the officials prompt names it: its name and its posts' labels."""

    name: str
    posts: List[str] = []


_PAGE_LABEL_RULES = """    - Everything the page uses to identify which office this person holds, written as one
      label. Collect both parts:
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
            -> "Council Member Place 3 (East Ward)"
        "District 1" on a page describing "one councilperson per district"
            -> "Council Member District 1"
    - Every seat belongs to a body, and its label needs that body's member title. Take the
      title from anywhere on the page: the page title, a section heading, or a sentence about
      the body. A heading directly above a person that is only a seat is not the title:
        "Ward 7" on a page titled "Mayor and Board of Selectmen"
            -> "Selectman Ward 7"
      A title naming several offices does not give all of them to everyone: only the person
      the page names as mayor is the mayor.
    - If the person holds more than one office, include every one in the same label, in the
      page's order. A second office often follows the name rather than preceding it:
        "Council Member Seat 4: Jane Roe, Vice Mayor"
            -> "Council Member Seat 4 and Vice Mayor\""""


def _bullets(items: List[str], indent: str) -> str:
    return "\n".join(f"{indent}- {item}" for item in items)


def _organization_scope(organization: PromptOrganization) -> str:
    """Naming the target body is the whole scope. Listing other bodies was tried (stage 5a) and
    added nothing on pages where each body has its own roster."""
    return f"""
    TARGET BODY
    Only extract people who hold a post in {organization.name}.
"""


def _pick_list_label_rules(organization: PromptOrganization, page_label_rules: str) -> str:
    return f"""    - Choose every post below that is this person's, and copy each exactly as written here —
      not as the page writes it:
{_bullets(organization.posts, "        ")}
    - A person can hold more than one, such as a seat and a presiding title. Put every one in the
      same label, joined with "and".
    - If the page gives them a {organization.name} title that is not listed, do not swap it for a
      listed post. Write that title from the page and join it with any listed posts they hold:
        "Deputy Mayor, Ward 5" when the list has "Council Member Ward 5" but no Deputy Mayor
            -> "Council Member Ward 5 and Deputy Mayor"
      Write a title from the page following these rules:
{page_label_rules}"""


# Note: Claude Sonnet 4.6 Generated prompt
def municipality_officials_prompt(
    known_roles: List[str],
    state: str = "",
    county: str | None = None,
    current_date: str | None = None,
    organization: PromptOrganization | None = None,
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
        roles_hint_str = (
            "- Known elected roles for this municipality: "
            + ", ".join(known_roles)
            + "."
        )

    jurisdiction_parts = [f"{county} County" if county else None, state]
    jurisdiction_context = ", ".join(p for p in jurisdiction_parts if p)
    jurisdiction_line = (
        f"\n    Jurisdiction: {jurisdiction_context}" if jurisdiction_context else ""
    )

    scope = _organization_scope(organization) if organization else ""
    label_rules = (
        _pick_list_label_rules(organization, _PAGE_LABEL_RULES) if organization else _PAGE_LABEL_RULES
    )

    return f"""
    You are a data extraction assistant. Extract information about the currently
    serving elected officials of the target municipality from the provided content.

    Current Date: {current_date}{jurisdiction_line}
{scope}
    STEP 1 - FIND OFFICIALS
    Only extract officials from:
    - A structured table, list, or directory of officials
    - A dedicated biography, about, or contact section for an official
    - A contact or position page for a single elected official, where the page or section
      heading names an elected role and the content includes the person's name and contact
      information, even if the body mostly describes the role's duties
    - A section labeled with a governing body name (e.g. "City Council Members", "Board of
      Aldermen") that lists names as headings or line items, even with no other details;
      take the role from the section heading
    Do NOT extract from news, event summaries, meeting notes, scattered mentions, or content
    recording what officials did (votes, minutes, ordinances, resolutions), even if structured.
    A list of links whose text is only a role or position label (e.g. "Mayor",
    "Councilmember, Place 1", "Alderman") is navigation, not a roster, and those labels are
    not person names.
    Only extract elected members of the governing body (e.g. Mayor, City Council, Board of
    Aldermen, Board of Commissioners). Exclude appointed staff and officials from other
    jurisdictions (county, precinct, special district), even when listed on the same page.
    Treat officials as currently serving unless the content says the roster is historical.
    If there are no valid sources, return an empty "people" array.

    STEP 2 - FOR EACH OFFICIAL, EXTRACT THE FOLLOWING
    Use null for any field the content does not give.

    name:
    - The person's name only, with every personal name component (honorifics, suffixes,
      generational markers: Dr., Hon., Jr., Sr., III) and no role or position labels.
    - Preserve name punctuation as-is: a "Last, First" comma is part of the name.
    - Only add an entry for a real person's name you can see. Never invent or infer one.

    image:
    - The image src of a profile photo, exactly as it appears in the content.

    label:
{label_rules}
    {roles_hint_str}

    phone, email:
    - Use in this order: the person's own, then their office's, then any general municipal
      contact found anywhere in the content.
    - An email must be a valid address (email@domain.tld). A contact form URL
      (e.g. /email-contact/node/...) is not an email; treat it as a url candidate.

    url:
    - Use in this order: official profile page, biography page, contact form URL, position
      listing page, general listing page.
    - Copy it exactly as it appears. Do not normalize, lowercase, or remove subdomains like "www".

    start_date, end_date:
    - start_date is the most recent election or appointment; end_date is when the current
      term expires.
    - Parse any written format (e.g. "Jan. 6, 2023", "January 2023", "2023") into "YYYY",
      "YYYY-MM", or "YYYY-MM-DD", as precise as the content allows.

    STEP 3 - RULES
    - Only use information present in the content. The one inference allowed is a title taken
      from a heading, page title or description, as described under label.
    - One entry per person. If the same person appears more than once, merge into one record.
    - All details must refer to the official's current term.
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


def page_covers_organization_prompt(
    organization_name: str,
    # That body's posts, to say what holding office in it looks like. A person is the evidence a
    # page covers a body, so the offices are the thing to recognise.
    posts: List[str],
    jurisdiction_name: str = "",
) -> str:
    """Whether one page carries people of one body.

    Asked once per body, after `relevant_page_prompt` has already said the page is worth reading
    and which links to follow. Deliberately not a list to choose from: picking one body out of
    several is the forced-match failure the officials prompt guards against, and it is invisible
    when it goes wrong, where a wrong yes/no about one body is one extraction run too many or too
    few.
    """
    jurisdiction_line = (
        f"    Municipality: {jurisdiction_name}\n" if jurisdiction_name else ""
    )
    posts_line = f"    Offices in it: {', '.join(posts)}\n" if posts else ""
    return f"""
    Decide whether the provided page content carries people who currently hold office in one
    specific governing body.

    Body: {organization_name}
{jurisdiction_line}{posts_line}
    Answer true only if this page presents a person holding office in that body as one of its
    officials — a roster entry, a directory row, a profile, or a contact block naming them.

    The test: would this page tell a reader who currently holds the office, if they had never
    heard of the person? A listing, a profile or a contact block answers that. A sentence about
    something that happened assumes you already know, and names the person in passing.

    All of these are false, however prominently the body or its people appear, and however many
    times a name is repeated:
    - a link to the body, or its name in the site navigation, including a heading such as
      "Connect with Elected Officials" that links elsewhere
    - a mention of the body in prose, or a meeting agenda or minutes naming it
    - news stories, press releases and announcements. "Mayor Wilson Signs Junk Fee Legislation
      into Law" names the mayor and their office and is still a report of an event: the page
      exists to say what happened, not who holds the office. A homepage carrying six such
      headlines is a newsfeed, not a roster.

    Judge the page's own content. A block that would be identical on every page of the site —
    a menu, a footer, a sidebar list of members repeated across a section — is furniture, and
    counting it would make every page of a site cover every body, which is no answer at all. The
    same list in the body of a page, as what that page exists to present, does count.

    Someone who holds office in that body counts even if the page gives them a title that is not
    among the offices listed above; the list is there to say what holding office in this body
    looks like, not to limit it.

    IMPORTANT: Return only valid JSON, {{"covers": true}} or {{"covers": false}}.
    """
