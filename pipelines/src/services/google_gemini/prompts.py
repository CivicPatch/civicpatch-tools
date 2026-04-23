from urllib.parse import urlparse

from shared.utils import config_utils
from shared.utils import id_utils


# jurisdiction_ocdid: ocdid of the jurisdiction to look up
# municipality_name: display name from config (e.g. "Hayes Township")
# stale_url: the URL currently on record, which may have moved to a new domain
def find_jurisdiction_url_prompt(jurisdiction_ocdid: str, municipality_name: str, stale_url: str | None = None) -> str:
    jurisdiction_ocdid_parts = id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
    county = jurisdiction_ocdid_parts.county
    state = id_utils.state_name(jurisdiction_ocdid)

    county_str = county.replace("_", " ").title() if county else None
    location_parts = [municipality_name, f"{county_str} County" if county_str else None, state]
    location_str = ", ".join(p for p in location_parts if p)

    stale_domain = urlparse(stale_url).netloc.removeprefix("www.") if stale_url else None
    stale_url_hint = (
        f"\n    The domain {stale_domain} no longer serves the official government website — do not return any URL on this domain. Find where the official government website is currently hosted."
        if stale_domain else ""
    )

    return f"""
    Find the official government website for this jurisdiction: {location_str}{stale_url_hint}

    Return the homepage URL of the official local government website
    (city hall, township, village, borough, etc.) specifically for {location_str}.
    Do not return news sites, Wikipedia, county portals, or unofficial directories.

    Return a JSON object:
    ```json
    {{ "url": "https://..." }}
    ```
    If you cannot find any official government website, return:
    ```json
    {{ "url": null }}
    ```

    IMPORTANT: Return only valid JSON. Do not include any other text.
    """


def research_municipality_prompt(jurisdiction_ocdid: str, municipality_name: str):
    jurisdiction_ocdid_parts = id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
    state = id_utils.state_name(jurisdiction_ocdid)
    county = jurisdiction_ocdid_parts.county
    designations = config_utils.get_designation_names()
    designations_str = ', '.join(designations)

    location_parts = [municipality_name, f"{county} County" if county else None, state]
    location_str = ", ".join(p for p in location_parts if p)

    return f"""
    Provide the current elected officials for the specified city, including the Mayor (if applicable)
    and other elected members of the local government. Format the response as a JSON object.

    Municipality: {location_str}

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
