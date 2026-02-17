from datetime import datetime
from typing import List
from jobs.people_collector.schemas import ResearchedPerson
import shared.utils.config_utils as config_utils

def relevant_page_prompt(page_url: str, _people_hint: List[ResearchedPerson]):
    prompt = f"""
    Your task is to determine if the provided content contains information about the **currently serving main officials** 
    of the target municipality. Main officials include roles such as Mayor, City Council Members, Aldermen, Select Board Members, 
    Commissioners, or other key elected or appointed officials who are part of the **primary governing body** of the municipality.

    Also consider the page URL: {page_url}
    It can be a strong indicator of relevance if it contains keywords like "officials", "government", "mayor", "council", "board", 
    or similar terms that suggest it is related to the municipality's governing body.

    **Relevant content includes:**
    - Structured listings (e.g., tables, lists, or directories) or dedicated sections (e.g., biography, contact, or about pages) 
      for the main officials of the municipality.
    - Pages that provide information about the current governing body, such as their names, roles, contact information, or biographies.

    **Irrelevant content includes:**
    - Pages that only mention auxiliary committees, department heads, supervisors, or other non-elected officials.
      For example: Planning and Zoning Committee, Parks and Recreation Board, etc.

    **Step-by-step instructions:**
    1. Scan the entire page content and identify ALL URLs/links present that could lead to pages 
        about the municipality's main governing officials (e.g., mayor, council, board). Collect these into a list.
    2. Determine whether the CURRENT page itself is relevant.
    3. Return the JSON output below.

    **Output Format:**
    Return a JSON object with the following fields:
    {{
        "relevant_urls": ["https://example.com/council", "https://example.com/mayor"],  # ALL links found on this page that may lead to main officials — even if the current page is not relevant
        "is_relevant": true/false,
        "thoughts": "Your reasoning goes here"
    }}

    **Critical rules:**
    - `relevant_urls` must be populated with ANY link on the page that could lead to information about the primary governing body, 
        regardless of whether the current page itself is relevant.
    - Do NOT leave `relevant_urls` empty if your reasoning mentions any URLs — they must appear in the list.
    - `relevant_urls` is for links FOUND ON THIS PAGE pointing elsewhere, not just the current page URL.
    """
    return prompt

def municipality_officials_prompt(
        _people_hint: List[ResearchedPerson]
    ):
    designation_names = config_utils.get_designation_names()
    designations_str = ", ".join(designation_names)
    current_date = datetime.now().strftime("%Y-%m-%d")

    #maybe_target_people = [p.name for p in (people_hint or []) if p.name]

    #if maybe_target_people:
    #    target_text = (
    #        f"Here is a list of known target people (may be missing or include extra): {', '.join(maybe_target_people)}"
    #    )
    #else:
    #    target_text = ""

    prompt = f"""
    Your task is to extract information about the currently serving elected officials
    of the target municipality.

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