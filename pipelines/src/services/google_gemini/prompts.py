from urllib.parse import urlparse

from shared.schemas import GovernmentForm
from shared.utils import id_utils
from shared.utils.government_forms import GOVERNMENT_FORM_DESCRIPTIONS

# A county's forms read differently from a city's: `commission` here is one board with no
# separate executive, not commissioners who each run a department.
COUNTY_GOVERNMENT_FORM_DESCRIPTIONS: dict[GovernmentForm, str] = {
    GovernmentForm.COMMISSION: "one elected board (commission, board of supervisors, commissioners "
    "court, police jury, legislature) and no separately elected executive",
    GovernmentForm.COUNCIL_MANAGER: "one elected board with an appointed administrator or manager",
    GovernmentForm.COUNTY_EXECUTIVE: "an elected board plus a separately elected county executive, "
    "mayor or parish president who does not sit on it",
}

_MUNICIPAL_TEST = (
    "The test between mayor_council and the one-board forms: does the chief executive sit and "
    "vote on the governing body? If they do, it is not mayor_council. Township committees, "
    "boards of supervisors or trustees, and New York towns and villages are township_board."
)
_COUNTY_TEST = (
    "A presiding county judge or chair who sits and votes on the board still counts as commission."
)


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


# Only ever called for a jurisdiction with no posts on record — once there are posts, they
# are the answer this would be asking for, already parsed and stored.
def research_municipality_prompt(jurisdiction_ocdid: str, municipality_name: str):
    jurisdiction_ocdid_parts = id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
    state = id_utils.state_name(jurisdiction_ocdid)
    county = jurisdiction_ocdid_parts.county
    location_parts = [municipality_name, f"{county} County" if county else None, state]
    location_str = ", ".join(p for p in location_parts if p)

    return f"""
    Provide the current elected officials for the specified city, including the Mayor (if applicable)
    and other elected members of the local government. Format the response as a JSON object.

    Municipality: {location_str}

    Instructions:

    1. Identify the elected officials in the local government,
       including the Mayor (if applicable).
       1.1. For each official, extract only:
            - name: Full name only (no titles)
            - label: The office they hold, exactly as the municipality writes it
              ("Council Member, Ward 3"). One string, not split into parts.
    3. Create a JSON object with the following structure:
       ```json
       {{
         "people": [
           {{
             "name": "Name of the official",
             "label": "Office as written"
           }}
         ]
       }}
       ```

    IMPORTANT: If the response contains anything other than a valid JSON object,
    it will be considered incorrect. Ensure the response is strictly JSON.
    Verify that the response is valid JSON before returning it.
    If it is not valid JSON, retry the generation.
    """


# forms: the forms the config files allow for this jurisdiction, so the answer is one of them
def municipal_government_form_prompt(
    jurisdiction_ocdid: str, municipality_name: str, forms: list[GovernmentForm]
) -> str:
    return _government_form_prompt(
        "municipality", _location(jurisdiction_ocdid, municipality_name), forms,
        GOVERNMENT_FORM_DESCRIPTIONS, _MUNICIPAL_TEST,
    )


# forms: the forms the config files allow for this county, so the answer is one of them
def county_government_form_prompt(
    jurisdiction_ocdid: str, county_name: str, forms: list[GovernmentForm]
) -> str:
    return _government_form_prompt(
        "county", _location(jurisdiction_ocdid, county_name), forms,
        COUNTY_GOVERNMENT_FORM_DESCRIPTIONS, _COUNTY_TEST,
    )


def _location(jurisdiction_ocdid: str, name: str) -> str:
    county = id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid).county
    county_str = f"{county.replace('_', ' ').title()} County" if county else None
    parts = [name, county_str if county_str and county_str.lower() != name.lower() else None]
    return ", ".join(p for p in [*parts, id_utils.state_name(jurisdiction_ocdid)] if p)


def _government_form_prompt(
    kind: str,
    location_str: str,
    forms: list[GovernmentForm],
    descriptions: dict[GovernmentForm, str],
    test: str,
) -> str:
    choices = "\n".join(f"    - {form.value}: {descriptions[form]}" for form in forms)
    return f"""
    Which form of government does this {kind} use: {location_str}

    Answer with exactly one of these values:
{choices}

    {test}

    Return a JSON object:
    ```json
    {{ "government_form": "<value>", "source": "<url you relied on>" }}
    ```

    IMPORTANT: Return only valid JSON. Do not include any other text.
    """
