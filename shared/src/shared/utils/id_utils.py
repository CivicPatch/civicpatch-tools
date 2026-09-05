import uuid

from shared.schemas import JurisdictionId

KNOWN_PLACE_KEYS = ["place", "special_district"]
# Not a place key: a county locates a place, or is the jurisdiction itself.
COUNTY_KEY = "county"

# The folder segment every per-jurisdiction data file sits under. Not the jurisdiction
# level: a county-only ocdid is level `counties` but still files under `local`.
DATA_SEGMENT = "local"

SAFE_CHARACTERS_MAP = {
    "~": "--",
}


def _encode_for_slug(value: str) -> str:
    for char, safe in SAFE_CHARACTERS_MAP.items():
        value = value.replace(char, safe)
    return value


def _decode_from_slug(value: str) -> str:
    for char, safe in SAFE_CHARACTERS_MAP.items():
        value = value.replace(safe, char)
    return value


def make_id():
    """A fresh id for whatever is being minted — a changeset, a run, a branch suffix."""
    return str(uuid.uuid4())


# Every jurisdiction ocdid starts with this, and a jurisdiction page's URL is its ocdid — so
# this is also how a route tells one from the older `{state}/local/{place}` folder form.
OCDID_PREFIX = "ocd-jurisdiction"


def parse_jurisdiction_ocdid(jurisdiction_ocdid: str) -> JurisdictionId:
    """
    Parses a jurisdiction ID. Supported shapes (all end in jurisdiction_type,
    e.g. "government"):

        ocd-jurisdiction/country:us/state:tx/government                                    (state-only)
        ocd-jurisdiction/country:us/state:tx/county:travis/government                      (county-only)
        ocd-jurisdiction/country:us/state:wa/place:seattle/government                      (place under state)
        ocd-jurisdiction/country:us/state:il/county:dupage/place:naperville/government     (place under county)

    For state-only and county-only, place_label/place stay None.
    Raises ValueError on any invalid shape.
    """
    try:
        components = jurisdiction_ocdid.split("/")
        result: dict = {}
        result["country"] = components[1].split(":")[1]
        result["state"] = components[2].split(":")[1]

        # Middle components between state and the trailing jurisdiction_type:
        # zero (state-only), one ("county:X" or "place:X"), or two ("county:X", "place:Y").
        middle = components[3:-1]
        for part in middle:
            label, value = part.split(":")
            if label == "county":
                result["county"] = value
            else:
                result["place_label"] = label
                result["place"] = value

        # Last component MUST be the jurisdiction type (no colon)
        jurisdiction_type = components[-1]
        if ":" in jurisdiction_type:
            raise ValueError("Invalid jurisdiction type format: contains ':'")

        return JurisdictionId(
            country=result["country"],
            state=result["state"],
            county=result.get("county"),
            place_label=result.get("place_label", "place"),
            place=result.get("place"),
            jurisdiction_type=jurisdiction_type,
        )
    except Exception as e:
        raise ValueError(
            f"Invalid jurisdiction ID format: {jurisdiction_ocdid}, error: {e}"
        ) from e


def jurisdiction_ocdid_to_folder(jurisdiction_ocdid: str) -> str:
    """
    Converts a jurisdiction ID to a reversible, human-friendly folder name.

    Examples:
      country:us/state:il/county:dupage/place:naperville/government
        -> "il/local/county_dupage__place_naperville"
      country:us/state:tx/county:travis/government
        -> "tx/local/county_travis"
      country:us/state:tx/government
        -> "tx"
    """

    parts = parse_jurisdiction_ocdid(jurisdiction_ocdid)

    # State-only: just the state code.
    if parts.county is None and parts.place is None:
        return parts.state

    folder = f"{parts.state}/{DATA_SEGMENT}/"
    if parts.county:
        folder += f"county_{parts.county}"
    if parts.place:
        if parts.county:
            folder += "__"
        folder += f"{parts.place_label}_{parts.place}"
    return folder


UNREVIEWED_SUFFIX = "-unreviewed"


def unreviewed_folder(folder: str) -> str:
    """Where a scrape lands before a human has approved it.

      "wa/local/place_seattle" -> "wa/local-unreviewed/place_seattle"

    A sibling of the reviewed level rather than a separate tree, so the two sit side by side
    in the repo. Derived here rather than upstream because the same jurisdiction has both a
    reviewed and an unreviewed path — review status is not a property of the ocdid.
    """
    segments = folder.split("/")
    if len(segments) != 3:
        raise ValueError(f"Not a per-jurisdiction data folder: {folder!r}")
    state, segment, place = segments
    return f"{state}/{segment}{UNREVIEWED_SUFFIX}/{place}"


def folder_to_jurisdiction_ocdid(folder: str) -> str:
    """
    Converts a folder path back to a jurisdiction ID.
    Inverse of jurisdiction_ocdid_to_folder.
    Example:
      "wa/local/place_seattle"
      -> "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
      "il/local/county_dupage__place_naperville"
      -> "ocd-jurisdiction/country:us/state:il/county:dupage/place:naperville/government"
      "tx/local/county_travis"
      -> "ocd-jurisdiction/country:us/state:tx/county:travis/government"
    """
    segments = folder.strip("/").split("/")
    if len(segments) < 3:
        raise ValueError(f"Invalid jurisdiction folder path: {folder}")

    state = segments[0]
    # segments[1] is DATA_SEGMENT — not needed to reconstruct ocdid
    place_segment = segments[2]
    ocdid = f"{OCDID_PREFIX}/country:us/state:{state}/"

    if "__" in place_segment:
        county_part, place_part = place_segment.split("__", 1)
        county = county_part.split("_", 1)[1]
        ocdid += f"county:{county}/"
    elif place_segment.startswith(f"{COUNTY_KEY}_"):
        county = place_segment.split("_", 1)[1]
        return f"{ocdid}{COUNTY_KEY}:{county}/government"
    else:
        place_part = place_segment

    place_found = False
    for key in KNOWN_PLACE_KEYS:
        if place_part.startswith(f"{key}_"):
            place = place_part[len(key) + 1 :]
            ocdid += f"{key}:{place}/government"
            place_found = True
            break

    if not place_found:
        raise ValueError(f"Unknown place key in folder segment: {place_part}")

    return ocdid


def jurisdiction_ocdid_to_slug(jurisdiction_ocdid: str) -> str:
    """
    Converts a jurisdiction ID to a reversible, human-friendly slug.
    Example:
      "ocd-jurisdiction/country:us/state:wa/place:seattle"
      -> "state_wa__place_seattle__government"
    """
    jurisdiction_ocdid_parts = parse_jurisdiction_ocdid(jurisdiction_ocdid)
    county = _encode_for_slug(jurisdiction_ocdid_parts.county or "")
    place = _encode_for_slug(jurisdiction_ocdid_parts.place or "")
    slug = f"state_{jurisdiction_ocdid_parts.state}__"
    if jurisdiction_ocdid_parts.county:
        slug += f"county_{county}__"
    if jurisdiction_ocdid_parts.place:
        slug += f"{jurisdiction_ocdid_parts.place_label}_{place}__"
    slug += jurisdiction_ocdid_parts.jurisdiction_type
    return slug.lower()


def make_git_branch(jurisdiction_ocdid: str, pipeline_run_id: str) -> str:
    """
    Converts a jurisdiction ID to a reversible, human-friendly git branch name.
    Example:
      "ocd-jurisdiction/country:us/state:wa/place:seattle"
      -> "2025-09-25-1a2b-state-wa-place-seattle"
    """
    slug = jurisdiction_ocdid_to_slug(jurisdiction_ocdid)
    return f"{pipeline_run_id}__{slug}".lower()


def _parse_slug_to_parts(slug: str) -> list[str]:
    """
    Helper function to parse slug components into OCD jurisdiction parts.

    Args:
        slug: The slug to parse (e.g., "state_ca__county_marin__place_seattle__government")

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
        county_value = _decode_from_slug(tokens[idx].split("_", 1)[1])
        result.append(f"county:{county_value}")
        idx += 1

    # Determine expected number of remaining tokens
    expected_remaining = 2

    # Process the place key (must be in KNOWN_PLACE_KEYS)
    if idx < len(tokens) and (len(tokens) - idx) >= expected_remaining:
        token = tokens[idx]
        place_found = False

        for key in KNOWN_PLACE_KEYS:
            if token.startswith(f"{key}_"):
                value = _decode_from_slug(token[len(key) + 1 :])
                result.append(f"{key}:{value}")
                idx += 1
                place_found = True
                break

        if not place_found:
            raise ValueError(f"Unknown place key in token: {token}")

    if idx == len(tokens) - 1:
        result.append(tokens[idx])
    else:
        raise ValueError(
            "Invalid slug format: too many segments or missing jurisdiction type."
        )

    return result


def slug_to_jurisdiction_ocdid(slug: str) -> str:
    """
    Converts a slug back to a full jurisdiction ID.

    Example:
        "state_ca__county_marin__place_seattle__government"
        -> "ocd-jurisdiction/country:us/state:ca/county:marin/place:seattle/government"
    """
    parts = _parse_slug_to_parts(slug)
    return "/".join(parts)


def state_name(jurisdiction_ocdid: str) -> str:
    jurisdiction_ocdid_parts = parse_jurisdiction_ocdid(jurisdiction_ocdid)
    state = jurisdiction_ocdid_parts.state

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
