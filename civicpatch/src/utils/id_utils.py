import re
import uuid
from datetime import datetime
from schemas import JurisdictionId

def make_request_id():
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    short_id = str(uuid.uuid4())[:4]
    return f"{date_str}-{short_id}"


def parse_jurisdiction_id(jurisdiction_id: str) -> JurisdictionId | None:
    """
    Parses a jurisdiction ID in the format 
        "ocd-jurisdiction/country:us/state:wa/place:seattle"
    OR
        "ocd-jurisdiction/country:us/state:il/county:dupage/place:naperville"
    and returns a JurisdictionId object.

    Returns None if the format is invalid.
    """
    components = jurisdiction_id.split("/")
    result = {}

    for component in components:
        if ":" in component:
            key, value = component.split(":", 1)
            result[key] = value.lower()
    
    if (
        "country" not in result or 
        "state" not in result or
        "place" not in result
    ):
        return None

    return JurisdictionId(
        country=result["country"],
        state=result["state"],
        county=result.get("county"),
        place=result["place"]
    )

def jurisdiction_id_to_slug(jurisdiction_id: str) -> str:
    jurisdiction_id_parts = parse_jurisdiction_id(jurisdiction_id)
    branch = f"state-{jurisdiction_id_parts.state}-"
    if jurisdiction_id_parts.county:
        branch += f"county-{jurisdiction_id_parts.county}-"
    branch += f"place-{jurisdiction_id_parts.place}"
    return branch

def jurisdiction_id_to_git_branch(jurisdiction_id: str, request_id: str) -> str:
    """
    Converts a jurisdiction ID to a reversible, human-friendly git branch name.
    Example:
      "ocd-jurisdiction/country:us/state:wa/place:seattle"
      -> "2025-09-25-1a2b-state-wa-place-seattle"
    """
    slug = jurisdiction_id_to_slug(jurisdiction_id)
    return f"{request_id}-{slug}"

def slug_to_jurisdiction_id(slug: str) -> str:
    """
    Converts a slug back to a jurisdiction ID.
    Example:
      "state-wa-place-seattle"
      -> "ocd-jurisdiction/country:us/state:wa/place:seattle"
      "state-il-county-dupage-place-naperville"
      -> "ocd-jurisdiction/country:us/state:il/county:dupage/place:naperville"
    """
    tokens = slug.split('-')
    idx = 0
    result = ["ocd-jurisdiction/country:us"]
    while idx < len(tokens):
        if tokens[idx] == "state":
            result.append(f"state:{tokens[idx+1]}")
            idx += 2
        elif tokens[idx] == "county":
            result.append(f"county:{tokens[idx+1]}")
            idx += 2
        elif tokens[idx] == "place":
            result.append(f"place:{tokens[idx+1]}")
            idx += 2
        else:
            idx += 1  # skip unknown tokens
    return "/".join(result)

def git_branch_to_jurisdiction_id(branch: str) -> str:
    """
    Converts a git branch name back to a jurisdiction ID.
    Example:
      "2025-09-25-1a2b-state-wa-place-seattle"
      -> "ocd-jurisdiction/country:us/state:wa/place:seattle"
      "2025-09-25-1a2b-state-il-county-dupage-place-naperville"
      -> "ocd-jurisdiction/country:us/state:il/county:dupage/place:naperville"
    """
    # Remove request_id prefix
    parts = branch.split('-', 3)
    if len(parts) < 4:
        raise ValueError("Branch name format invalid: {branch}")
    rest = parts[3]  # e.g. "state-wa-place-seattle" or "state-il-county-dupage-place-naperville"
    tokens = rest.split('-')
    idx = 0
    result = ["ocd-jurisdiction/country:us"]
    while idx < len(tokens):
        if tokens[idx] == "state":
            result.append(f"state:{tokens[idx+1]}")
            idx += 2
        elif tokens[idx] == "county":
            result.append(f"county:{tokens[idx+1]}")
            idx += 2
        elif tokens[idx] == "place":
            result.append(f"place:{tokens[idx+1]}")
            idx += 2
        else:
            idx += 1  # skip unknown tokens
    return "/".join(result)

def jurisdiction_id_to_folder(jurisdiction_id: str) -> str:
    """
    Converts a jurisdiction ID to a reversible, human-friendly folder name.
    Example:
      {
        country: "us",
        state: "il",
        county: "dupage",
        place: "naperville"
      }
      -> "il/dupage/naperville"
    """

    jurisdiction_id_parts = parse_jurisdiction_id(jurisdiction_id)

    folder = f"{jurisdiction_id_parts.state}/"
    if jurisdiction_id_parts.county:
        folder += f"{jurisdiction_id_parts.county}/"
    folder += jurisdiction_id_parts.place

    return folder

def state_name(jurisdiction_id: str) -> str:
    jurisdiction_id_parts = parse_jurisdiction_id(jurisdiction_id)
    state = jurisdiction_id_parts.state

    state_names = {
        "al": "Alabama",
        "ak": "Alaska",
        "az": "Arizona",
        "ar": "Arkansas",
        "ca": "California",
        "co": "Colorado",
        "ct": "Connecticut",
        "de": "Delaware",
        "fl": "Florida",
        "ga": "Georgia",
        "hi": "Hawaii",
        "id": "Idaho",
        "il": "Illinois",
        "in": "Indiana",
        "ia": "Iowa",
        "ks": "Kansas",
        "ky": "Kentucky",
        "la": "Louisiana",
        "me": "Maine",
        "md": "Maryland",
        "ma": "Massachusetts",
        "mi": "Michigan",
        "mn": "Minnesota",
        "ms": "Mississippi",
        "mo": "Missouri",
        "mt": "Montana",
        "ne": "Nebraska",
        "nv": "Nevada",
        "nh": "New Hampshire",
        "nj": "New Jersey",
        "nm": "New Mexico",
        "ny": "New York",
        "nc": "North Carolina",
        "nd": "North Dakota",
        "oh": "Ohio",
        "ok": "Oklahoma",
        "or": "Oregon",
        "pa": "Pennsylvania",
        "ri": "Rhode Island",
        "sc": "South Carolina",
        "sd": "South Dakota",
        "tn": "Tennessee",
        "tx": "Texas",
        "ut": "Utah",
        "vt": "Vermont",
        "va": "Virginia",
        "wa": "Washington",
        "wv": "West Virginia",
        "wi": "Wisconsin",
        "wy": "Wyoming"
    }

    return state_names.get(state, "Unknown")