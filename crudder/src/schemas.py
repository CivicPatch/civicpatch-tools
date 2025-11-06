from typing import Optional

from pydantic import BaseModel, model_validator

KNOWN_PLACE_KEYS = ["place", "special_district"]


class Representative(BaseModel):
    name: str

    class Config:
        extra = "allow"


class PullRequest(BaseModel):
    branch_name: str
    jurisdiction_id: str = ""

    @model_validator(mode="after")
    def set_jurisdiction_id(self):
        if not self.jurisdiction_id and self.branch_name:
            self.jurisdiction_id = git_branch_to_jurisdiction_id(self.branch_name)
        return self


class Jurisdiction(BaseModel):
    id: str
    name: str
    url: str | None


class JurisdictionId(BaseModel):
    country: str
    state: str
    county: Optional[str] = None
    place_label: str = "place"
    place: str
    jurisdiction_type: str


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
    # Remove request_id prefix
    parts = branch.split("__", 1)
    if len(parts) < 2:
        raise ValueError(f"Branch name format invalid: {branch}")

    # Extract the jurisdiction part of the branch name
    rest = parts[1]  # e.g., "state_wa__place_seattle__government"
    tokens = rest.split("__")

    result = ["ocd-jurisdiction/country:us"]
    idx = 0

    # State is always the first key
    if idx < len(tokens) and tokens[idx].startswith("state_"):
        state_value = tokens[idx].split("_", 1)[1]
        result.append(f"state:{state_value}")
        idx += 1
    else:
        raise ValueError("Branch must start with 'state'.")

    # County is optional
    if idx < len(tokens) and tokens[idx].startswith("county_"):
        county_value = tokens[idx].split("_", 1)[1]
        result.append(f"county:{county_value}")
        idx += 1

    # Process the place key (must be in KNOWN_PLACE_KEYS)
    if idx < len(tokens) and any(
        tokens[idx].startswith(f"{key}_") for key in KNOWN_PLACE_KEYS
    ):
        key, value = tokens[idx].split("_", 1)
        if key in KNOWN_PLACE_KEYS:
            result.append(f"{key}:{value}")
            idx += 1
        else:
            raise ValueError(f"Unknown place key: {key}")

    # The last token is the jurisdiction type
    if idx == len(tokens) - 1:
        result.append(tokens[idx])
    else:
        raise ValueError(
            "Invalid branch format: too many segments or missing jurisdiction type."
        )

    return "/".join(result).lower()
