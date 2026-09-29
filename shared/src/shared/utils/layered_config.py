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


class GovernmentFormConfig(BaseModel):
    # A name ending in one of these gets only the government forms carrying it: "town" in Massachusetts.
    suffixes: list[str] = []
    organizations: list[DerivedOrganization] = []


GovernmentFormsConfig = dict[GovernmentForm, GovernmentFormConfig]


class ConfigFile(BaseModel):
    """One `data_source/.../config.yml`: the country's roles (`data_source/config.yml`), the
    country's government forms for one level, or one state's roles and government forms for one level."""

    roles: list[ConfigRole] = []
    government_forms: GovernmentFormsConfig = {}

    @model_validator(mode="after")
    def _roles_are_distinct(self) -> "ConfigFile":
        _check_roles_distinct(self.roles)
        return self


class MergedConfig(BaseModel):
    """What a jurisdiction in one state and level uses: the country's file plus its state's."""

    roles: RoleConfig
    country_government_forms: GovernmentFormsConfig
    state_government_forms: GovernmentFormsConfig


def merged_config(
    country_roles: ConfigFile, country_government_forms: ConfigFile, state: ConfigFile | None
) -> MergedConfig:
    state = state or ConfigFile()
    if country_roles.government_forms or country_government_forms.roles:
        raise ValueError("country roles and country government forms belong in separate files")
    config_roles = [*country_roles.roles, *state.roles]
    _check_roles_distinct(config_roles)
    _check_country_government_forms(country_government_forms.government_forms)
    _check_state_government_forms(state.government_forms, country_government_forms.government_forms)
    merged = MergedConfig(
        roles=RoleConfig(
            roles=[_role(config_role, priority) for priority, config_role in enumerate(config_roles)]
        ),
        country_government_forms=country_government_forms.government_forms,
        state_government_forms=state.government_forms,
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


def allowed_government_forms(config: MergedConfig, name: str) -> list[GovernmentForm]:
    """State government forms for the name's suffix, then the state's other government forms, then the same from the
    country. A state that lists government forms without suffixes narrows to them."""
    suffix = name_suffix(name)
    for government_forms in (config.state_government_forms, config.country_government_forms):
        for_suffix = [government_form for government_form, form_config in government_forms.items() if suffix in form_config.suffixes]
        if for_suffix:
            return for_suffix
        for_any_name = [government_form for government_form, form_config in government_forms.items() if not form_config.suffixes]
        if for_any_name:
            return for_any_name
    return []


def government_form_organizations(config: MergedConfig, government_form: GovernmentForm) -> list[DerivedOrganization]:
    state_form = config.state_government_forms.get(government_form)
    if state_form is not None and state_form.organizations:
        return state_form.organizations
    return config.country_government_forms[government_form].organizations


def resolve_government_form(
    config: MergedConfig, name: str, government_form: GovernmentForm | None
) -> GovernmentForm | None:
    """The saved government form, else the only allowed one, else unknown."""
    if government_form is not None:
        return government_form
    government_forms = allowed_government_forms(config, name)
    if len(government_forms) == 1:
        return government_forms[0]
    return None


def derived_organizations(
    config: MergedConfig, government_form: GovernmentForm | None
) -> list[DerivedOrganization]:
    """Nothing until the government form is known, or for one saved at the wrong level."""
    if government_form is None or government_form not in config.country_government_forms:
        return []
    return government_form_organizations(config, government_form)


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


def _check_country_government_forms(government_forms: GovernmentFormsConfig) -> None:
    for government_form, form_config in government_forms.items():
        if not form_config.organizations:
            raise ValueError(f"country government form {government_form.value} has no organizations")


def _check_state_government_forms(state_government_forms: GovernmentFormsConfig, country_government_forms: GovernmentFormsConfig) -> None:
    for government_form in state_government_forms:
        if government_form not in country_government_forms:
            raise ValueError(f"{government_form.value} is not a government form at this level")


def _check_role_labels_resolve(config: MergedConfig) -> None:
    names = {
        lookup_key(name) for role in config.roles.roles for name in [role.label, *role.aliases]
    }
    for government_forms in (config.country_government_forms, config.state_government_forms):
        for government_form, form_config in government_forms.items():
            for organization in form_config.organizations:
                for label in organization.role_labels:
                    if lookup_key(label) not in names:
                        raise ValueError(
                            f"{government_form.value}: {organization.name}'s role {label!r} is not a role"
                        )


def _check_one_organization_per_role(config: MergedConfig) -> None:
    """Research files a role into the first organization whose role labels hold it, which is
    only right while that organization is the only one."""
    for government_form in config.country_government_forms:
        seen: set[str] = set()
        for organization in government_form_organizations(config, government_form):
            for label in organization.role_labels:
                if label in seen:
                    raise ValueError(f"{government_form.value}: {label!r} is in two organizations")
                seen.add(label)
