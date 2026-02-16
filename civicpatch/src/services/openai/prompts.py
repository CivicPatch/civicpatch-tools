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
    Your task is to extract information about the currently serving elected officials
    of the target municipality.

    {target_text}

    Treat officials as currently serving when they appear in a structured roster 
    that is presented as the municipality's governing body, unless
    the content clearly indicates the roster is historical or past.

    Roles (examples): Mayor, Council Member, Aldermen, Select Board Member, Commissioner
    Target designations: {designations_str}
    Current Date: {current_date}

    Return a JSON object in the following format:
    - people: (Array of objects) Each object should have:
      - name: (String) Full name only (no titles). If the role is vacant, use "Vacant Vacant" as the name.
      - image: (String or null) URL to profile image (https://...)
      - roles: (Array of strings) Active municipal roles
      - designations: (Array) 
            Designation labels should ALWAYS be in the format of <designation_type> <designation value/name>, 
            If no designation type is provided, leave empty.
      - phone: (String or null) Formatted phone number (personal phone > office phone > general contact number for municipality)
      - email: (String or null) Formatted email in form email@domain.tld (personal email > office email > general contact email for municipality)
      - url: (String or null) Formatted URL (https://...). (official's profile > biography URL > contact form email URL > related position listing > general listing)
      - start_date: (String or null) "YYYY" or "YYYY-MM" or "YYYY-MM-DD"
      - end_date: (String or null) "YYYY" or "YYYY-MM" or "YYYY-MM-DD"
    - thoughts: (String) Your reasoning process

    **Instructions:**
    - Extract phone numbers, email addresses, and URLs even if they are not part of a structured listing or dedicated section, as long as they are explicitly present in the text.
    - Ensure all extracted details refer to the **current term** of the official.
    - Ensure only ONE entry exists per unique person's name. Merge all extracted details for the same person into a single record.
    """
    return prompt