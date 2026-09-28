from pydantic import BaseModel, model_validator
from shared.schemas import GovernmentForm, JurisdictionLevel, KnownOrganization
from shared.utils import config_utils


class DerivedOrganization(BaseModel):
    name: str
    role_labels: list[str]


# One line each, shown to the LLM next to the form's name. The test between mayor_council and
# the one-board forms is whether the chief executive sits and votes on the governing body.
GOVERNMENT_FORM_DESCRIPTIONS: dict[GovernmentForm, str] = {
    GovernmentForm.MAYOR_COUNCIL: "a council plus a separately elected mayor who does not sit on it",
    GovernmentForm.COUNCIL_MANAGER: "a council with an appointed manager; any mayor sits on the council",
    GovernmentForm.COMMISSION: "elected commissioners who together govern and each head a department",
    GovernmentForm.TOWNSHIP_BOARD: "one elected board whose presiding officer sits and votes on it",
    GovernmentForm.OPEN_TOWN_MEETING: "a select board or board of selectmen, with an open town meeting",
    GovernmentForm.REPRESENTATIVE_TOWN_MEETING: "a select board, with elected town meeting members",
    GovernmentForm.COUNTY_EXECUTIVE: "a county board plus a separately elected county executive",
}


def describe_government_form(form: GovernmentForm) -> str:
    """open_town_meeting -> "open town meeting (a select board or board of selectmen, ...)"."""
    return f"{form.value.replace('_', ' ')} ({GOVERNMENT_FORM_DESCRIPTIONS[form]})"


ANY_SUFFIX = "*"

FormsBySuffix = dict[str, list[GovernmentForm]]


class GovernmentFormsConfig(BaseModel):
    """`config/government_forms.yml`: which forms are allowed, by level and name suffix."""

    country: dict[JurisdictionLevel, FormsBySuffix]
    states: dict[str, dict[JurisdictionLevel, FormsBySuffix]] = {}

    @model_validator(mode="after")
    def _states_narrow_the_country(self) -> "GovernmentFormsConfig":
        for level, by_suffix in self.country.items():
            if ANY_SUFFIX not in by_suffix:
                raise ValueError(f"country.{level} needs a {ANY_SUFFIX!r} entry")
        for state, levels in self.states.items():
            for level, by_suffix in levels.items():
                if level not in self.country:
                    raise ValueError(
                        f"states.{state}.{level}: no country forms for {level}"
                    )
                everything = self.country[level][ANY_SUFFIX]
                for suffix, forms in by_suffix.items():
                    for form in forms:
                        if form not in everything:
                            raise ValueError(
                                f"states.{state}.{level}.{suffix}: {form} is not a {level} form"
                            )
        return self


def load_government_forms_config() -> GovernmentFormsConfig:
    return GovernmentFormsConfig.model_validate(config_utils.get_government_forms())


# Role labels as the taxonomy spells them; test_government_forms checks each one resolves.
_ORGANIZATIONS_BY_FORM: dict[GovernmentForm, list[DerivedOrganization]] = {
    GovernmentForm.MAYOR_COUNCIL: [
        DerivedOrganization(name="Council", role_labels=["Council Member"]),
        DerivedOrganization(name="Office of the Mayor", role_labels=["Mayor"]),
    ],
    GovernmentForm.COUNCIL_MANAGER: [
        DerivedOrganization(name="Council", role_labels=["Council Member", "Mayor"]),
    ],
    GovernmentForm.COMMISSION: [
        DerivedOrganization(name="Commission", role_labels=["Commissioner", "Mayor"]),
    ],
    GovernmentForm.TOWNSHIP_BOARD: [
        DerivedOrganization(
            name="Board", role_labels=["Supervisor", "Clerk", "Treasurer", "Trustee"]
        ),
    ],
    GovernmentForm.OPEN_TOWN_MEETING: [
        DerivedOrganization(
            name="Select Board",
            role_labels=[
                "Select Board Chair",
                "Select Board Vice Chair",
                "Select Board Member",
            ],
        ),
        DerivedOrganization(name="Town Meeting", role_labels=["Moderator"]),
    ],
    GovernmentForm.REPRESENTATIVE_TOWN_MEETING: [
        DerivedOrganization(
            name="Select Board",
            role_labels=[
                "Select Board Chair",
                "Select Board Vice Chair",
                "Select Board Member",
            ],
        ),
        DerivedOrganization(
            name="Town Meeting", role_labels=["Moderator", "Town Meeting Member"]
        ),
    ],
    GovernmentForm.COUNTY_EXECUTIVE: [
        DerivedOrganization(name="Council", role_labels=["Council Member"]),
        DerivedOrganization(name="County Executive", role_labels=["County Executive"]),
    ],
}


def organizations_for(form: GovernmentForm) -> list[DerivedOrganization]:
    return _ORGANIZATIONS_BY_FORM[form]


def derived_organization_for_role(
    form: GovernmentForm, role_label: str
) -> DerivedOrganization | None:
    for organization in organizations_for(form):
        if role_label in organization.role_labels:
            return organization
    return None


def office_labels(
    organization: KnownOrganization, form: GovernmentForm | None
) -> list[str]:
    """What holding office in this organization looks like: its posts' labels, or on a cold
    start, before any post exists, the role labels its form derives under the same name."""
    if organization.posts:
        return [post.label for post in organization.posts]
    if form is None:
        return []
    for derived in organizations_for(form):
        if derived.name == organization.name:
            return derived.role_labels
    return []


def name_suffix(name: str) -> str:
    """Millbury town -> town: the statutory type most registry names end with."""
    words = name.split()
    return words[-1].lower() if words else ""


def allowed_forms(
    config: GovernmentFormsConfig, state: str, level: JurisdictionLevel, name: str
) -> list[GovernmentForm]:
    if level not in config.country:
        raise ValueError(f"no government forms for level {level!r}")
    suffix = name_suffix(name)

    state_forms = config.states.get(state, {}).get(level, {})
    if suffix in state_forms:
        return state_forms[suffix]
    if ANY_SUFFIX in state_forms:
        return state_forms[ANY_SUFFIX]

    country_forms = config.country[level]
    if suffix in country_forms:
        return country_forms[suffix]
    return country_forms[ANY_SUFFIX]


def resolve_government_form(
    config: GovernmentFormsConfig,
    state: str,
    level: JurisdictionLevel,
    name: str,
    government_form: GovernmentForm | None,
) -> GovernmentForm | None:
    if government_form is not None:
        return government_form
    forms = allowed_forms(config, state, level, name)
    if len(forms) == 1:
        return forms[0]
    return None
