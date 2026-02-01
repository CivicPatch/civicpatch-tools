from datetime import datetime
from typing import List
from jobs.people_collector.schemas import ResearchedPerson
import shared.utils.config_utils as config_utils

def relevant_page_prompt(people_hint: List[ResearchedPerson]):
    """
    Generate a prompt to determine if a page is relevant for extracting municipality officials.
    """

    maybe_target_people = [p.name for p in (people_hint or []) if p.name]

    if maybe_target_people:
        target_text = (
            f"Here is a list of known target people (may be missing or include extra): {', '.join(maybe_target_people)}"
        )
    else:
        target_text = ""

    prompt = f"""
    Your task is to determine if the provided content contains information about the current officials of the target municipality. This includes structured listings (e.g., tables, lists, or directories) or dedicated sections (e.g., biography, contact, or about pages) for officials.

    {target_text}

    Only consider people who are currently serving as officials. 
    Do not include anyone who is described as former, past, resigned, deceased, 
    or otherwise not currently in office.

    Return a JSON object with "thoughts" explaining your reasoning in the following format:
    {{
        "thoughts": "Your reasoning goes here",
        "related_urls": [],  # List any URLs that are likely to contain more information about the officials or lead to a listing
        "is_relevant": true
    }}

    **Guidelines for Identifying Relevant URLs:**
    - Include URLs that are likely to contain structured listings or dedicated sections about officials.
    - Exclude URLs that are general or unrelated, such as homepages, news articles, event summaries, or meeting minutes.
    - Focus on pages that are likely to provide detailed information about officials, such as directories, biographies, or contact pages.
    """
    return prompt

def municipality_officials_prompt(
        people_hint: List[ResearchedPerson]
    ):
    designation_names = config_utils.get_designation_names()
    designations_str = ", ".join(designation_names)
    current_date = datetime.now().strftime("%Y-%m-%d")

    maybe_target_people = [p.name for p in (people_hint or []) if p.name]

    if maybe_target_people:
        target_text = (
            f"Here is a list of known target people (may be missing or include extra): {', '.join(maybe_target_people)}"
        )
    else:
        target_text = ""

    prompt = f"""
    Your task is to extract information about the **current** elected officials of the target municipality.

    {target_text}

    Only extract people who are currently serving as officials as of {current_date}. 
    Do not include anyone who is described as former, past, resigned, deceased, 
    or otherwise not currently in office.

    First, determine if the content contains a **structured listing** (such as a table, list, or directory) of officials, or a **dedicated biography/about/contact section** for an official. If not, return an empty JSON array `[]`.

    Roles (examples): Mayor, Council Member, Aldermen, Select Board Member, Commissioner
    Target designations: {designations_str}
    Current Date: {current_date}

    Return a JSON object in the following format:
    - people: (Array of objects) Each object should have:
      - name: (String) Full name only (no titles)
      - image: (String or null) URL to profile image (https://...)
      - roles: (Array of strings) Active municipal roles
      - designations: (Array) 
            Example: ["Ward 1", "District 2, Seat 8"]
      - phone: (String or null) Formatted phone number
      - email: (String or null) Email address in the format of email@domain.tld
      - url: (String or null) In order of importance: the official's profile, biography URL, contact form URL, related position listing, or null if none exist.
      - start_date: (String or null) "YYYY" or "YYYY-MM" or "YYYY-MM-DD"
      - end_date: (String or null) "YYYY" or "YYYY-MM" or "YYYY-MM-DD"
    - thoughts: (String) Your reasoning process
 
    **Instructions:**
    - Only extract officials if their information appears in a **structured listing** (e.g., table, list, or directory) or in a **dedicated biography/about/contact section**.
    - A **structured listing** must explicitly include names and roles. Additional details (e.g., contact information, designations, or term dates) are optional but preferred.
    - **Do NOT extract officials based on mentions in news articles, event summaries, meeting notes, or scattered references throughout the content.**
    - **Do NOT extract officials if the only evidence is a link, heading, or navigation item (e.g., "Mayor And Council") without an actual structured listing or dedicated section in the provided content.**
    - **Do NOT extract officials based on contextual clues such as dates, roles, or ongoing activities unless they are explicitly part of a structured listing or dedicated section.**
    - If the only mentions of officials are within news stories, event recaps, meeting summaries, or scattered throughout the text (not in a structured list or dedicated section), return an empty array.
    - Do NOT infer or guess officials' names or roles from context, prior knowledge, or recent mentions. Only extract if the information is presented in a structured way or in a dedicated section.
    - Do NOT infer information for officials. Only extract what is explicitly stated (ex: emails).
    - Do NOT include people whose terms have ended, resigned, vacated their roles, or are deceased.
    - Ensure only ONE entry exists per unique person's name. Merge all extracted details for the same person into a single record.

    **Examples of what NOT to extract:**
    - "Mayor John Smith attended the ribbon-cutting ceremony for the new library."
    - "Councilwoman Jane Doe was quoted in a news article about the town's budget."
    - "Deputy Mayor Joe Bloggs was present at the community event on March 3, 2024."
    - "Mayor and Council" is mentioned as a link or heading, but no structured listing or dedicated section is present.

    **Examples of what to extract:**
    - A table listing officials with their names and roles (e.g., "John Smith - Mayor, Jane Doe - Councilwoman").
    - A section titled "Mayor and Council" that includes a list of officials with their roles, contact details, and/or biographies.

    **FINAL MANDATORY CHECK:** Review your entire response for accuracy before submitting, paying close attention to the role inference, date extraction, and term identification rules.
    """
    return prompt