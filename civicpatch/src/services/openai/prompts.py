from datetime import datetime
import utils.config_utils as config_utils

def municipality_officials_prompt(government_type, people_hint):
    """
    Generate a single prompt string for extracting city officials, following the detailed Ruby and Gemini logic.
    If people_hint has exactly one entry, treat that as person_name for targeting.
    """

    roles = config_utils.get_roles_by_government_type(government_type)
    division_names = config_utils.get_divisions()
    current_date = datetime.now().strftime("%Y-%m-%d")

    maybe_target_people = [p.get("name") for p in (people_hint or []) if p.get("name")]

    if len(maybe_target_people) == 1:
        person_name = maybe_target_people[0]
        target_text = f"the person named '{person_name}'"
    elif maybe_target_people:
        person_name = ""
        target_text = (
            f"any of the main governing body of a municipality. "
            f"Here is a list of known target people (may be missing or include extra): {', '.join(maybe_target_people)}"
        )
    else:
        person_name = ""
        target_text = "any of the main governing body of a municipality."

    content_type = (
        f"First, determine if the content contains relevant information about {target_text}.\n"
        "If not, return an empty JSON array `[]`."
    )

    prompt = f"""
You are an expert data extractor focused on accuracy.

{content_type}

Target Person (if applicable): {person_name}
Target roles: {', '.join(roles)}
Target divisions: ward, district
Current Date: {current_date}

Return a JSON object.

Output Field Definitions & Structure:
- name: (String) Full name only (no titles).
- image: (String or null) URL to profile image (https://...)
- roles: (Array of strings) Active municipal roles.
         Identify their official job title or specific position.
         This can be a wide variety of municipal roles (e.g., "Mayor", "City Manager", "Selectman",
         "Alderman", "Council Member").
- divisions: (Array of strings) Specific district/ward and name/number,
          only if specified (e.g., "Ward 1", "District 2").
- phone_number: (String or null) Formatted phone number
- email: (String or null) Email address (email@example.com)
- website: (String or null) Website URL (http(s)://...)
- start_date: (String or null) "YYYY" or "YYYY-MM" or "YYYY-MM-DD"
- end_date: (String or null) "YYYY" or "YYYY-MM" or "YYYY-MM-DD"

Extraction Guidelines:
- Roles extraction:
  - Extract roles that match the **target roles** provided (e.g., {', '.join(roles)}).
  - If a role includes additional descriptors or variations, normalize it to the closest matching target role when possible.
    - Example: "Vice President" under a governing body → Normalize to the closest matching target role, such as "Council Vice President" or "Commissioner Vice President."
    - If a role cannot be normalized to a target role but is clearly valid (e.g., "Vice President"), extract it as-is.
  - Use the governing body or surrounding context to determine the correct role for ambiguous titles.
    - Example: If "Vice President" is listed under "Council Members," infer it as "Council Vice President."
    - Example: If "Vice President" appears without clear context, extract it as "Vice President."
  - Include only active roles (today is {current_date}).

- Divisions:
  - Extract divisions if explicitly mentioned and relevant to the person's role.
  - Do not infer divisions if they are not explicitly stated.

- General Guidelines:
  - Merge details for the same person into a single record.
  - Assign confidence (0-1 scale) and provide a brief reason for each field's data.
  - Extract full names only (e.g., "John Smith," not "Mayor John Smith"). Titles belong in the roles field.
  - Ensure extracted data is accurate and relevant to the governing body or target roles.
- Image: Extract URL of portrait/headshot near name. Ignore logos, banners, icons. Check alt text but prioritize proximity/style.
- Contact Details (Phone/Email/Website):
  - Associate details logically if near the person's name/section.
  - Pick the most relevant contact detail if multiple are present.
  - Phone numbers:
    - Extract number after labels like "Office:", "Cell:", "Mobile:", "Direct:", "Home:". Exclude "Fax:". Format numbers simply.
  - Markdown Links: Extract email/phone from the VISIBLE TEXT of links like `[TEXT](...)`, ignore the target URL.
  - `website` data MUST be a valid http/https URL. Prefer profile pages. EXCLUDE mailto:, tel:.
  - `email` data should ONLY contain email addresses.
- Term Dates (`start_date`, `end_date`):
  - Extract start_date and end_date in YYYY, YYYY-MM, or YYYY-MM-DD format.
  - Acceptable date phrases include:
    - “Elected [date]”, “Appointed [date]”, “Term: [date1] to [date2]”, “Since [date]”.
    - For vague phrases like "Spring 2025", extract the year only.
  - If more than one term is mentioned, extract the most recent term dates.
  - Examples:
    - "Elected Nov 2024 for term ending Dec 2028" -> start_date: "2024-11", end_date: "2028-12"
    - "Served January 2018 until December 2021 - Re-elected and serving January 2022 and until December 2025" -> start_date: "2022-01", end_date: "2025-12"
    - "Elected in 2017 and re-elected in 2021 for the 2022-2025 term." -> start_date: "2022", end_date: "2025"

**FINAL MANDATORY CHECK**: Review your entire response for accuracy before submitting,
  paying close attention to the role inference, date extraction, and term identification rules.
"""
    return prompt