import re

from pydantic import BaseModel, model_validator
from shared.schemas import GovernmentForm, JurisdictionLevel, Role, RoleConfig
from shared.utils.government_forms import DerivedOrganization, name_suffix
from shared.utils.taxonomy import lookup_key

COUNTRY_ROLES_PATH = "data_source/config.yml"
# Every layer's file. Mirrored by CONFIG_PATH in open-data's scripts/github_actions/merge_config_pr.py.
CONFIG_PATH = re.compile(r"^data_source/(([a-z]{2}/)?(local|counties)/)?config\.yml$")


def country_forms_path(level: JurisdictionLevel) -> str:
    return f"data_source/{level}/config.yml"


def state_config_path(state: str, level: JurisdictionLevel) -> str:
    return f"data_source/{state}/{level}/config.yml"


class ConfigRole(BaseModel):
    id: str
    label: str
    is_unique: bool = False
    aliases: list[str] = []


class FormConfig(BaseModel):
    # A name ending in one of these gets only the forms carrying it: "town" in Massachusetts.
    suffixes: list[str] = []
    organizations: list[DerivedOrganization] = []


FormsConfig = dict[GovernmentForm, FormConfig]


class ConfigFile(BaseModel):
    """One `data_source/.../config.yml`: the country's roles (`data_source/config.yml`), the
    country's forms for one level, or one state's roles and forms for one level."""

    roles: list[ConfigRole] = []
    government_forms: FormsConfig = {}

    @model_validator(mode="after")
    def _roles_are_distinct(self) -> "ConfigFile":
        _check_roles_distinct(self.roles)
        return self


class MergedConfig(BaseModel):
    """What a jurisdiction in one state and level uses: the country's file plus its state's."""

    roles: RoleConfig
    country_forms: FormsConfig
    state_forms: FormsConfig


def merged_config(
    country_roles: ConfigFile, country_forms: ConfigFile, state: ConfigFile | None
) -> MergedConfig:
    state = state or ConfigFile()
    if country_roles.government_forms or country_forms.roles:
        raise ValueError("country roles and country forms belong in separate files")
    config_roles = [*country_roles.roles, *state.roles]
    _check_roles_distinct(config_roles)
    _check_country_forms(country_forms.government_forms)
    _check_state_forms(state.government_forms, country_forms.government_forms)
    merged = MergedConfig(
        roles=RoleConfig(
            roles=[_role(config_role, priority) for priority, config_role in enumerate(config_roles)]
        ),
        country_forms=country_forms.government_forms,
        state_forms=state.government_forms,
    )
    _check_role_labels_resolve(merged)
    _check_one_organization_per_role(merged)
    return merged


def jurisdiction_config(
    configs: dict[str, ConfigFile], state: str, level: JurisdictionLevel
) -> MergedConfig:
    """The merged config for one state and level, from every stored file keyed by its path."""
    return merged_config(
        configs.get(COUNTRY_ROLES_PATH, ConfigFile()),
        configs.get(country_forms_path(level), ConfigFile()),
        configs.get(state_config_path(state, level)),
    )


def check_roles_distinct_across(files: list[ConfigFile]) -> None:
    """Role ids are global and the database keeps one alias per label, so no two files may
    share an id, label or alias, even files that never merge."""
    _check_roles_distinct([role for file in files for role in file.roles])


def allowed_forms(config: MergedConfig, name: str) -> list[GovernmentForm]:
    """State forms for the name's suffix, then the state's other forms, then the same from the
    country. A state that lists forms without suffixes narrows to them."""
    suffix = name_suffix(name)
    for forms in (config.state_forms, config.country_forms):
        for_suffix = [form for form, form_config in forms.items() if suffix in form_config.suffixes]
        if for_suffix:
            return for_suffix
        for_any_name = [form for form, form_config in forms.items() if not form_config.suffixes]
        if for_any_name:
            return for_any_name
    return []


def form_organizations(config: MergedConfig, form: GovernmentForm) -> list[DerivedOrganization]:
    state_form = config.state_forms.get(form)
    if state_form is not None and state_form.organizations:
        return state_form.organizations
    return config.country_forms[form].organizations


def resolve_government_form(
    config: MergedConfig, name: str, government_form: GovernmentForm | None
) -> GovernmentForm | None:
    """The saved form, else the only allowed one, else unknown."""
    if government_form is not None:
        return government_form
    forms = allowed_forms(config, name)
    if len(forms) == 1:
        return forms[0]
    return None


def derived_organizations(
    config: MergedConfig, government_form: GovernmentForm | None
) -> list[DerivedOrganization]:
    """Nothing until the form is known, or for a form saved at the wrong level."""
    if government_form is None or government_form not in config.country_forms:
        return []
    return form_organizations(config, government_form)


def _role(config_role: ConfigRole, priority: int) -> Role:
    return Role(
        id=config_role.id,
        label=config_role.label,
        is_unique=config_role.is_unique,
        priority=priority,
        aliases=config_role.aliases,
    )


def _check_roles_distinct(roles: list[ConfigRole]) -> None:
    ids: set[str] = set()
    names: dict[str, str] = {}
    for role in roles:
        if role.id in ids:
            raise ValueError(f"role id {role.id!r} is listed twice")
        ids.add(role.id)
        for name in [role.label, *role.aliases]:
            key = lookup_key(name)
            if key in names and names[key] != role.id:
                raise ValueError(f"{name!r} names both {names[key]!r} and {role.id!r}")
            names[key] = role.id


def _check_country_forms(forms: FormsConfig) -> None:
    for form, form_config in forms.items():
        if not form_config.organizations:
            raise ValueError(f"country form {form.value} has no organizations")


def _check_state_forms(state_forms: FormsConfig, country_forms: FormsConfig) -> None:
    for form in state_forms:
        if form not in country_forms:
            raise ValueError(f"{form.value} is not a form at this level")


def _check_role_labels_resolve(config: MergedConfig) -> None:
    names = {
        lookup_key(name) for role in config.roles.roles for name in [role.label, *role.aliases]
    }
    for forms in (config.country_forms, config.state_forms):
        for form, form_config in forms.items():
            for organization in form_config.organizations:
                for label in organization.role_labels:
                    if lookup_key(label) not in names:
                        raise ValueError(
                            f"{form.value}: {organization.name}'s role {label!r} is not a role"
                        )


def _check_one_organization_per_role(config: MergedConfig) -> None:
    """Research files a role into the first organization whose role labels hold it, which is
    only right while that organization is the only one."""
    for form in config.country_forms:
        seen: set[str] = set()
        for organization in form_organizations(config, form):
            for label in organization.role_labels:
                if label in seen:
                    raise ValueError(f"{form.value}: {label!r} is in two organizations")
                seen.add(label)
