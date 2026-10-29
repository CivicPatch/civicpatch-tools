from datetime import datetime
from typing import List

from shared.schemas import GovernmentForm, JurisdictionLevel
from shared.utils.government_forms import describe_government_form


def relevant_page_prompt(
    page_url: str,
    jurisdiction_name: str = "",
    known_roles: List[str] = [],
    # The bodies cp.org already holds for this jurisdiction, by name. Without them the rules
    # below rule out an Office of the Mayor page as a department: Jackson TN's lives at
    # `/government/mayorsoffice`, a sibling of `/government/departments/*`, and reads exactly
    # like the auxiliary pages the Irrelevant section is written to reject.
    known_organizations: List[str] = [],
    # The jurisdiction's form, when one is saved or decided by the config. It tells the model
    # which bodies govern here, so a School Committee under an open town meeting is not one.
    government_form: GovernmentForm | None = None,
):
    jurisdiction_line = (
        f"    Target jurisdiction: {jurisdiction_name}\n" if jurisdiction_name else ""
    )
    government_form_line = (
        f"    Government form: {describe_government_form(government_form)}\n"
        if government_form
        else ""
    )
    # The generic list only when nothing is known: a cold start whose research found nobody.
    # Otherwise the roles cp.org holds or research named, so a School Committee chair is not read
    # as a main official just because "chair" sounds like one.
    main_officials = (
        f"""Main officials hold one of this municipality's listed offices, elected or appointed:
    {", ".join(known_roles)}. An office the page shows is elected counts too; appointed or hired
    staff on no list do not."""
        if known_roles
        else """Main officials are the Mayor, City Council Members, Aldermen, Select Board Members,
    Commissioners and others who make up the municipality's **primary governing body**, and any
    other office the page shows is elected. Appointed or hired staff are not main officials."""
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

    {main_officials}

    Page URL: {page_url}
{jurisdiction_line}{government_form_line}{known_organizations_line}
    The URL tells you which links share the municipality's domain. It tells you nothing about
    `is_relevant`, which comes from the page content alone.

    ---

    ## is_relevant

    True when the page exists to show who currently holds one of these offices: a roster, a
    directory, or one official's own page. Ask "does this page exist to show who holds office
    right now?" and answer on the page's own heading and body.

    Also true, and these are the ones most often got wrong:
    - The heading names one of these offices and the page gives a person's name for it. A
      site-wide navigation menu is not the page's purpose however much of the content it fills,
      and a non-voting deputy appearing alongside does not change the answer.
    - The page lists the municipality's own officials and also lists appointed staff. A small
      town's "City Officials" page naming the Mayor and council members alongside the City
      Manager, Water Supervisor and Fire Chief is the roster. Judge it by whether the governing
      body's members are presented as such, not by who else shares the page.
    - A staff or contact directory that gives a row to a current holder of one of these offices,
      such as the Mayor or Town Clerk with a phone number and email. That row is a directory entry for the official,
      even when every other row is staff.{known_organizations_rule}

    When a page names a person who holds one of the roles above and you cannot tell whether it is
    a roster or a department landing page, answer true. The two mistakes do not cost the same: a
    page wrongly called relevant costs one extraction that returns nobody, while a page wrongly
    called irrelevant is never read again and its officials are never found.

    False for these, whoever is named in them:
    - Committees, boards and commissions that are not among this municipality's bodies (Planning
      and Zoning, Parks and Recreation, Airport Advisory, unless listed above), and pages about
      department heads or other staff who hold none of these offices. A Mayor or Alderman sitting
      on such a body does not make its page relevant.
    - Special districts, utility boards and other sub-municipal entities (Water Supply District,
      Fire District), which are separate legal entities. A structured roster of their board
      members is still not this municipality's.
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
    - a governing body or office ("Township Board", "City Council", "Mayor", "City Officials",
      "Board of Trustees", "Aldermen", "Commissioners", "Select Board", "Town Clerk")
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


NO_ORGANIZATION = "none"


def _organization_field(choices: List[str]) -> str:
    """The body each person is listed under, as the page writes it; code matches it to ours.
    Empty when the run knows no bodies to match against."""
    if not choices:
        return ""
    listed = "\n".join(f'        - "{choice}"' for choice in choices)
    return f"""    organization_label:
    - The heading, label or page title this person is listed under, copied exactly as the
      page writes it (e.g. "Lister Board", "Mayor and Township Committee"); null when there
      is none.
    - For reference, the bodies the law provides for (this government may have fewer):
{listed}

"""


def _roles_hint(
    known_roles: List[str], divisions: List[str], government_form_role_labels: List[str]
) -> str:
    lines = []
    if known_roles:
        lines.append("- Roles in this municipality: " + ", ".join(known_roles) + ".")
    if government_form_role_labels:
        lines.append(
            "- Roles the law provides for (this municipality may fill fewer): "
            + ", ".join(government_form_role_labels)
            + "."
        )
    if divisions:
        lines.append("- Divisions in this municipality: " + ", ".join(divisions) + ".")
    return "\n    ".join(lines)


_GOVERNING_BODY = """they are a member of the governing body (e.g. Mayor, City Council, Board of Aldermen,
      Board of Commissioners)"""
_LEFT_OUT = """officials of
    other governments (another city or county, the state, a precinct or special district), even
    when listed on the same page."""


def _who_to_extract(roles_listed: bool, organizations_listed: bool) -> str:
    """Only what we told the model or the page states outright: the governing body and the listed
    offices. Its own judgement of an unlisted title (elected or staff?) flips read to read, so an
    unlisted office waits for its state's config to list it."""
    ways = [
        _GOVERNING_BODY,
        'their title is one of the roles listed under label below (a longer form of one counts:\n'
        '      "Treasurer/Tax Collector" is the Treasurer)' if roles_listed else "",
        "they hold a seat on one of the bodies listed under organization" if organizations_listed else "",
    ]
    listed = ";\n    - ".join(way for way in ways if way)
    return f"""Extract a person only if:
    - {listed}.
    Anyone else stays out, elected or not: a title on no list (deputies, assistants, directors,
    chiefs, coordinators, department staff, a clerk or manager not listed), and {_LEFT_OUT}"""


# Note: Claude Sonnet 4.6 Generated prompt
_TARGET_NOUN = {
    JurisdictionLevel.LOCAL: "municipality",
    JurisdictionLevel.COUNTIES: "county",
    JurisdictionLevel.STATE: "state",
}
_TARGET_ADJECTIVE = {
    JurisdictionLevel.LOCAL: "municipal",
    JurisdictionLevel.COUNTIES: "county",
    JurisdictionLevel.STATE: "state",
}


def _jurisdiction_line(level: JurisdictionLevel, state: str, county: str | None) -> str:
    """A county in a town's ocdid locates the town; at county level it is the target itself."""
    if level == JurisdictionLevel.LOCAL and county:
        context = f"a municipality in {county} County, {state}"
    else:
        context = ", ".join(part for part in [f"{county} County" if county else None, state] if part)
    return f"\n    Jurisdiction: {context}" if context else ""


def elected_officials_prompt(
    known_roles: List[str],
    level: JurisdictionLevel,
    state: str = "",
    county: str | None = None,
    current_date: str | None = None,
    divisions: List[str] = [],
    government_form_role_labels: List[str] = [],
    # The jurisdiction's organizations a person may be put in, the default left out.
    organization_choices: List[str] = [],
):
    """
    Generate a prompt for extracting a jurisdiction's elected officials (Llama-optimized).

    `current_date` is an argument because the prompt asks for *currently serving*
    officials: reading the clock in here made the prompt a function of wall-time, so the
    same input produced a different prompt every day and evals silently drifted as terms
    expired. Production leaves it None and gets today; evals pin it.
    """
    current_date = current_date or datetime.now().strftime("%Y-%m-%d")

    roles_hint_str = _roles_hint(known_roles, divisions, government_form_role_labels)

    jurisdiction_line = _jurisdiction_line(level, state, county)

    return f"""
    You are a data extraction assistant. Extract information about the currently
    serving officials of the target {_TARGET_NOUN[level]} from the provided content.

    Current Date: {current_date}{jurisdiction_line}

    STEP 1 - FIND OFFICIALS
    Only extract officials from:
    - A structured table, list, or directory of officials
    - A dedicated biography, about, or contact section for an official
    - A contact or position page for a single official, where the page or section
      heading names an office and the content includes the person's name and contact
      information, even if the body mostly describes the role's duties
    - A section labeled with a governing body name (e.g. "City Council Members", "Board of
      Aldermen") that lists names as headings or line items, even with no other details;
      take the role from the section heading
    Do NOT extract from news, event summaries, meeting notes, scattered mentions, or content
    recording what officials did (votes, minutes, ordinances, resolutions), even if structured.
    A list of links whose text is only a role or position label (e.g. "Mayor",
    "Councilmember, Place 1", "Alderman") is navigation, not a roster, and those labels are
    not person names.
    {_who_to_extract(bool(known_roles or government_form_role_labels), bool(organization_choices))}
    Treat officials as currently serving unless the content says the roster is historical, or
    gives a term that ended before the current date: leave those people out.
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
{_PAGE_LABEL_RULES}
    {roles_hint_str}

{_organization_field(organization_choices)}    phone, email:
    - Use in this order: the person's own, then their office's, then any general
      {_TARGET_ADJECTIVE[level]} contact found anywhere in the content.
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


def governing_sections_prompt() -> str:
    """Which sections of a long charter or statute to read: asked of the headings alone, sent as
    the content, one per line after an id like H0017 and grouped under their subchapters. The id
    is not the section number: shown a list index, the model answered with the § number."""
    return """
    Below are the section headings of a municipal or county charter or statute, one per line, each
    after an id like H0017 (the id is not the section number), grouped under their subchapters.

    Which sections say how the governing body is composed and elected, how the chief executive is
    chosen, how the governing body picks its presiding officers, who presides at a town or village
    meeting, and how the jurisdiction's other officers are elected or appointed? Appointments are
    often listed under the powers and duties of the governing body, the chief executive or the
    manager, so include those sections; include any section whose heading names an office (Clerk,
    Treasurer, Assessor, Attorney), and every section of a subchapter about officers, whatever its
    heading. Include a section when in doubt. Leave out finance, utilities, boards and
    commissions, and other procedure.

    Return {"sections": [...]} with the ids exactly as written, for example "H0017".
    """


def governing_law_reader_prompt() -> str:
    """The instructions for every question about one jurisdiction's law. The law, then one
    question, is the content: the law stays the same across a run's questions, so it is the
    cached prefix and only the question changes."""
    return """
    You read a municipal or county charter, or the state statutes that govern a municipality, and
    answer one question about it. The law is given first, under "# Charter" and "# General law"
    when both are present: the charter governs, and the general law applies where the charter
    says nothing. Answer only from the text. Never answer from what such governments usually do.

    How an office is filled, as the text says:
    - elected_by_voters: the voters elect or choose the person to that office, as a town or
      village does at its annual meeting.
    - elected_by_members: a body chooses one of its own members for it (a chair, a mayor chosen
      by the council), whatever verb the text uses: "appoint from among the board" is this.
    - appointed: a body or officer appoints, hires or employs the person, who need not be one of
      its members.
    - not_stated: the text names the office but not how it is filled.

    The quote must be copied exactly from the text: one continuous passage, a few words to a
    sentence, from the clause that answers the question. Never join separate passages and never
    shorten one with "..." or "[...]". Prefer a short quote. If the text does not answer, say so;
    do not guess.

    IMPORTANT: Return only valid JSON. Do not include any other text.
    """


def governing_role_question(role_label: str, organization_name: str) -> str:
    """One role, named as the organization does; the law may write it otherwise ("Selectboard
    member"), and the answer's label says how."""
    return f"""
    Question: does this law establish the office of {role_label}, by that name or another, and
    how is it filled? It is asked for as part of the {organization_name}; an office the law makes
    an officer of the town, city or village itself counts too.

    Return {{"established": ..., "label": ..., "filled_by": ..., "maximum_memberships": ...,
    "quote": ...}}: established false, label "", filled_by "not_stated", maximum_memberships
    null and quote "" when the law does not establish it; otherwise label is the office's name as
    the law writes it, and maximum_memberships the number of people who hold it when the law
    states one, else null.
    """


def governing_presiding_question(organization_name: str, candidates: List[tuple[str, List[str]]]) -> str:
    """Offices most laws never set up, asked together: one question for all of them, not one
    each. `candidates` is each office's id and the names the law may write it by."""
    listed = "\n".join(f"    - {role_id}: {', '.join(names)}" for role_id, names in candidates)
    return f"""
    Question: which of these offices of the {organization_name} does this law establish, and how
    is each filled? An office the law makes an officer of the town, city or village itself counts
    too. Each is listed as its id, then the names it may go by:
{listed}

    Return {{"offices": [{{"role_id": ..., "label": ..., "filled_by": ..., "maximum_memberships":
    ..., "quote": ...}}]}}, one entry per office the law establishes and none for the others, an
    empty list when it establishes none. role_id is the id listed above; label is the office's
    name as the law writes it; maximum_memberships the number of people who hold it when the law
    states one, else null. Each quote is its own office's clause.
    """


# Measured 2026-10-28 on 85 organization labels: without this rule the model places a fund's or a
# neighbouring village's trustees on the lookalike board; with it, no wrong placement.
_ORGANIZATION_MATCH_RULE = """A heading names a body only if it is that body under another
    wording. It is "{none}" when it is a fund, a library, a building, a programme, a
    department, an office held by one person, a committee or commission not on the list, or
    a body of another town, village, city or county, even one that shares the website."""
_ORGANIZATION_MATCH_EXAMPLES = """Examples: "Assessor Board" with [Board of Assessors, Board of
    Health] is "Board of Assessors". "Smith Memorial Fund Trustees" with [Trustees of Trust
    Funds, Select Board] is "{none}": a fund's own trustees. "North Village Commissioners" for
    the village of South with [Board of Commissioners] is "{none}": another village."""


def organization_match_prompt() -> str:
    """The system prompt for `organization_match_question`; a system message alone gets an
    empty answer from the model, so the question goes as content."""
    return f"""
    You match the heading a local government's web page lists people under to one of that
    government's own bodies, or to none.

    {_ORGANIZATION_MATCH_RULE.format(none=NO_ORGANIZATION)}
    {_ORGANIZATION_MATCH_EXAMPLES.format(none=NO_ORGANIZATION)}

    IMPORTANT: Return only valid JSON. Do not include any other text.
    """


def organization_match_question(place_name: str, organization_label: str, choices: List[str]) -> str:
    """Asked once per organization label the words could not settle. The default is never
    offered; a label naming none leaves the title to decide."""
    listed = "\n".join(f'    - "{choice}"' for choice in choices)
    return f"""
    A page of {place_name} lists people under the heading "{organization_label}". Which of these
    bodies of {place_name} is that, if any?
{listed}

    Return {{"organization": ...}}: exactly one name from the list, or "{NO_ORGANIZATION}".
    """
