import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

KNOWN_PLACE_KEYS = ["place", "special_district"]


class JurisdictionId(BaseModel):
    country: str
    state: str
    county: Optional[str] = None
    place_label: str = "place"
    place: str
    jurisdiction_type: str


def make_request_id():
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    short_id = str(uuid.uuid4())[:4]
    return f"{date_str}-{short_id}"


def parse_jurisdiction_id(jurisdiction_id: str) -> JurisdictionId | None:
    """
    Parses a jurisdiction ID in the format
        "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
    OR
        "ocd-jurisdiction/country:us/state:il/county:dupage/place:naperville/government"
    and returns a JurisdictionId object.

    Returns None if the format is invalid.
    """
    try:
        components = jurisdiction_id.split("/")
        result = {}
        country_part = components[1]
        result["country"] = country_part.split(":")[1]

        state_part = components[2]
        result["state"] = state_part.split(":")[1]

        substate_part = components[3]
        substate_label, substate_name = substate_part.split(":")
        if substate_label == "county":
            result["county"] = substate_name
            place_label, place_name = components[4].split(":")
            result["place_label"] = place_label
            result["place"] = place_name
        else:
            result["place_label"] = substate_label
            result["place"] = substate_name

        # Last component MUST contain the jurisdiction type
        # Which has no ":"
        jurisdiction_type = components[-1]
        if ":" in jurisdiction_type:
            return None

        if "country" not in result or "state" not in result:
            return None

        return JurisdictionId(
            country=result["country"],
            state=result["state"],
            county=result.get("county", None),
            place_label=result["place_label"],
            place=result["place"],
            jurisdiction_type=jurisdiction_type,
        )
    except Exception as e:
        print(f"Error: {e}")
        return None


def jurisdiction_id_to_folder(jurisdiction_id: str) -> str:
    """
    Converts a jurisdiction ID to a reversible, human-friendly folder name.
    Example:
      {
        country: "us",
        state: "il",
        county: "dupage", (optional)
        place: "naperville_test",
        jurisdiction_type: "council"
      }
      -> "il/county_dupage__place_naperville"
    """

    jurisdiction_id_parts = parse_jurisdiction_id(jurisdiction_id)

    folder = f"{jurisdiction_id_parts.state}/"
    if jurisdiction_id_parts.county:
        folder += f"county_{jurisdiction_id_parts.county}__"
    folder += f"{jurisdiction_id_parts.place_label}_{jurisdiction_id_parts.place}"

    return folder


def jurisdiction_id_to_slug(jurisdiction_id: str) -> str:
    jurisdiction_id_parts = parse_jurisdiction_id(jurisdiction_id)
    branch = f"state_{jurisdiction_id_parts.state}__"
    if jurisdiction_id_parts.county:
        branch += f"county_{jurisdiction_id_parts.county}__"
    branch += f"{jurisdiction_id_parts.place_label}_{jurisdiction_id_parts.place}__"
    branch += f"{jurisdiction_id_parts.jurisdiction_type}"
    return branch.lower()


def jurisdiction_id_to_git_branch(jurisdiction_id: str, request_id: str) -> str:
    """
    Converts a jurisdiction ID to a reversible, human-friendly git branch name.
    Example:
      "ocd-jurisdiction/country:us/state:wa/place:seattle"
      -> "2025-09-25-1a2b-state-wa-place-seattle"
    """
    slug = jurisdiction_id_to_slug(jurisdiction_id)
    return f"{request_id}__{slug}".lower()


def _parse_slug_to_parts(slug: str, include_jurisdiction_type: bool) -> list[str]:
    """
    Helper function to parse slug components into OCD jurisdiction parts.

    Args:
        slug: The slug to parse (e.g., "state_ca__county_marin__place_seattle__government")
        include_jurisdiction_type: Whether to include the final jurisdiction type segment

    Returns:
        List of jurisdiction parts to be joined with "/"
    """
    tokens = slug.split("__")
    result = ["ocd-jurisdiction/country:us"]

    # State is always the first key
    if not tokens[0].startswith("state_"):
        raise ValueError("Slug must start with 'state'.")

    state_value = tokens[0].split("_", 1)[1]
    result.append(f"state:{state_value}")

    idx = 1

    # County is optional
    if idx < len(tokens) and tokens[idx].startswith("county_"):
        county_value = tokens[idx].split("_", 1)[1]
        result.append(f"county:{county_value}")
        idx += 1

    # Determine expected number of remaining tokens
    expected_remaining = 2 if include_jurisdiction_type else 1

    # Process the place key (must be in KNOWN_PLACE_KEYS)
    if idx < len(tokens) and (len(tokens) - idx) >= expected_remaining:
        token = tokens[idx]
        place_found = False

        for key in KNOWN_PLACE_KEYS:
            if token.startswith(f"{key}_"):
                value = token[len(key) + 1 :]
                result.append(f"{key}:{value}")
                idx += 1
                place_found = True
                break

        if not place_found:
            raise ValueError(f"Unknown place key in token: {token}")

    # Handle the jurisdiction type if required
    if include_jurisdiction_type:
        if idx == len(tokens) - 1:
            result.append(tokens[idx])
        else:
            raise ValueError(
                "Invalid slug format: too many segments or missing jurisdiction type."
            )
    elif idx != len(tokens):
        raise ValueError(
            f"Invalid slug format: expected {idx} tokens but got {len(tokens)}."
        )

    return result


def slug_to_jurisdiction_id(slug: str) -> str:
    """
    Converts a slug back to a full jurisdiction ID.

    Example:
        "state_ca__county_marin__place_seattle__government"
        -> "ocd-jurisdiction/country:us/state:ca/county:marin/place:seattle/government"
    """
    parts = _parse_slug_to_parts(slug, include_jurisdiction_type=True)
    return "/".join(parts)


def git_branch_to_jurisdiction_id(branch: str) -> str:
    """
    Converts a git branch name back to a jurisdiction ID.

    Example:
        "2025-09-25-1a2b__state_wa__place_seattle__government"
        -> "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
        "2025-09-25-1a2b__state_il__county_dupage__place_naperville__government"
        -> "ocd-jurisdiction/country:us/state:il/county:dupage/place:naperville/government"
        "2025-09-25-1a2b__state_ca__county_marin__special_district__marin_city_community_services_district__governing_board"
        -> "ocd-jurisdiction/country:us/state:ca/county:marin/special_district:marin_city_community_services_district/governing_board"
    """
    # Remove request_id prefix to get the slug
    parts = branch.split("__", 1)
    if len(parts) < 2:
        raise ValueError(f"Branch name format invalid: {branch}")

    slug = parts[1]  # e.g., "state_wa__place_seattle__government"
    return slug_to_jurisdiction_id(slug).lower()


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
        "dc": "Washington, D.C.",
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
        "wy": "Wyoming",
    }

    return state_names.get(state, "Unknown")
