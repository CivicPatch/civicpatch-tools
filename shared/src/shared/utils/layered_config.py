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
    """Role ids and labels are global, so no two files may share one, even files that never
    merge. An alias may repeat across roles and files."""
    _check_roles_distinct([role for file in files for role in file.roles])


def allowed_government_forms(config: MergedConfig, name: str) -> list[GovernmentForm]:
    """The state's government forms for the name's suffix, then its other ones, then the same from
    the country. A state that lists government forms without suffixes narrows to them."""
    suffix = name_suffix(name)
    for government_forms in (config.state_government_forms, config.country_government_forms):
        for_suffix = [
            government_form
            for government_form, government_form_config in government_forms.items()
            if suffix in government_form_config.suffixes
        ]
        if for_suffix:
            return in_standard_order(for_suffix)
        for_any_name = [
            government_form
            for government_form, government_form_config in government_forms.items()
            if not government_form_config.suffixes
        ]
        if for_any_name:
            return in_standard_order(for_any_name)
    return []


def in_standard_order(government_forms) -> list[GovernmentForm]:
    """As the enum lists them. Stored config comes back from jsonb, which does not keep key order."""
    order = list(GovernmentForm)
    return sorted(government_forms, key=order.index)


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
    role_id_by_label: dict[str, str] = {}
    for role in roles:
        if role.id in ids:
            raise ValueError(f"role id {role.id!r} is listed twice")
        ids.add(role.id)
        key = lookup_key(role.label)
        if key in role_id_by_label:
            raise ValueError(f"{role.label!r} names both {role_id_by_label[key]!r} and {role.id!r}")
        role_id_by_label[key] = role.id
    # An alias may name several roles (the record's organization breaks the tie), but never
    # another role's label: a label names exactly one role.
    for role in roles:
        for alias in role.aliases:
            owner = role_id_by_label.get(lookup_key(alias))
            if owner is not None and owner != role.id:
                raise ValueError(f"{alias!r} names both {owner!r} and {role.id!r}")


def _check_country_government_forms(government_forms: GovernmentFormsConfig) -> None:
    for government_form, form_config in government_forms.items():
        if not form_config.organizations:
            raise ValueError(f"country government form {government_form.value} has no organizations")


def _check_state_government_forms(state_government_forms: GovernmentFormsConfig, country_government_forms: GovernmentFormsConfig) -> None:
    for government_form in state_government_forms:
        if government_form not in country_government_forms:
            raise ValueError(f"{government_form.value} is not a government form at this level")


def _check_role_labels_resolve(config: MergedConfig) -> None:
    """A role label, not an alias: an alias may name several roles, so it cannot say which."""
    labels = {lookup_key(role.label) for role in config.roles.roles}
    for government_form, organization in _every_organization(config):
        for label in organization.role_labels:
            if lookup_key(label) not in labels:
                raise ValueError(
                    f"{government_form.value}: {organization.name}'s role {label!r} is not a role's label"
                )


def _every_organization(config: MergedConfig):
    for government_forms in (config.country_government_forms, config.state_government_forms):
        for government_form, form_config in government_forms.items():
            for organization in form_config.organizations:
                yield government_form, organization


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
