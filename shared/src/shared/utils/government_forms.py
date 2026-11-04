import re

from pydantic import BaseModel
from shared.schemas import GovernmentForm


class DerivedOrganization(BaseModel):
    name: str
    role_labels: list[str]


# One line each, shown to the LLM next to the form's name. The test between mayor_council and
# the one-board forms is whether the chief executive sits and votes on the governing body.
GOVERNMENT_FORM_DESCRIPTIONS: dict[GovernmentForm, str] = {
    GovernmentForm.MAYOR_COUNCIL: "a council plus a separately elected mayor who does not sit on it",
    GovernmentForm.COUNCIL_MANAGER: "a council; a mayor, if there is one, sits on it; with or without an appointed manager",
    GovernmentForm.COMMISSION: "elected commissioners who together govern and each head a department",
    GovernmentForm.TOWNSHIP_BOARD: "one elected board whose presiding officer sits and votes on it",
    GovernmentForm.OPEN_TOWN_MEETING: "a select board or board of selectmen, with an open town meeting",
    GovernmentForm.REPRESENTATIVE_TOWN_MEETING: "a select board, with elected town meeting members",
    GovernmentForm.COUNTY_EXECUTIVE: "a county board plus a separately elected county executive",
    GovernmentForm.VILLAGE_BOARD: "an elected board of trustees with a president who sits and votes on it",
    GovernmentForm.COUNTY_COURT: "a county court: an elected county judge who presides and votes, with elected commissioners",
}


def government_form_name(form: GovernmentForm) -> str:
    """open_town_meeting -> "open town meeting"."""
    return form.value.replace("_", " ")


def describe_government_form(form: GovernmentForm) -> str:
    """open_town_meeting -> "open town meeting (a select board or board of selectmen, ...)"."""
    return f"{government_form_name(form)} ({GOVERNMENT_FORM_DESCRIPTIONS[form]})"


PARENTHETICAL = re.compile(r"\s*\([^)]*\)")


def name_suffix(name: str) -> str:
    """Millbury town -> town: the statutory type most registry names end with. A parenthetical
    is not part of it: "Reno city (Lamar County)" and "San Buenaventura (Ventura) city" -> city."""
    words = PARENTHETICAL.sub("", name).split()
    return words[-1].lower() if words else ""


LEGAL_STATUS_WORDS = ("city", "town", "township", "county", "village", "borough", "plantation")
DEFAULT_ORGANIZATION_SUFFIX = "Officers"
LSAD_PLACEHOLDER = "{lsad}"


def organization_name(name: str, jurisdiction_name: str) -> str:
    """"{lsad} Council" for "Lakeview town" -> "Town Council"; the placeholder and its space drop
    out when the name ends in no legal status word."""
    suffix = name_suffix(jurisdiction_name)
    lsad = suffix.capitalize() if suffix in LEGAL_STATUS_WORDS else ""
    return name.replace(f"{LSAD_PLACEHOLDER} ", f"{lsad} " if lsad else "")


def default_organization_name(jurisdiction_name: str) -> str:
    """"Essex town" -> "Town Officers"; names that end in no legal status word -> "Officers"."""
    return organization_name(f"{LSAD_PLACEHOLDER} {DEFAULT_ORGANIZATION_SUFFIX}", jurisdiction_name)
