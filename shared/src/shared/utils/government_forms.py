from pydantic import BaseModel
from shared.schemas import GovernmentForm, KnownOrganization


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
}


def government_form_name(form: GovernmentForm) -> str:
    """open_town_meeting -> "open town meeting"."""
    return form.value.replace("_", " ")


def describe_government_form(form: GovernmentForm) -> str:
    """open_town_meeting -> "open town meeting (a select board or board of selectmen, ...)"."""
    return f"{government_form_name(form)} ({GOVERNMENT_FORM_DESCRIPTIONS[form]})"


def office_labels(organization: KnownOrganization) -> list[str]:
    """What holding office in this organization looks like: its posts' labels, or on a cold
    start, before any post exists, its derived role labels."""
    if organization.posts:
        return [post.label for post in organization.posts]
    return organization.role_labels


def name_suffix(name: str) -> str:
    """Millbury town -> town: the statutory type most registry names end with."""
    words = name.split()
    return words[-1].lower() if words else ""
