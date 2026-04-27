import pytest
from shared.utils.config_utils import RoleConfig, RoleEntry, merge_role_configs, load_role_config_for_jurisdiction


def _make_config(roles=None) -> RoleConfig:
    return RoleConfig(roles=[RoleEntry(**r) for r in (roles or [])])


# --- merge_role_configs ---

def test_merge_role_configs_accumulates_roles():
    base = _make_config(roles=[{"role": "mayor"}, {"role": "council member"}])
    state = _make_config(roles=[{"role": "supervisor"}])
    result = merge_role_configs(base, state)
    role_names = {e.role.lower() for e in result.roles}
    assert role_names == {"mayor", "council member", "supervisor"}


def test_merge_role_configs_more_specific_wins():
    base = _make_config(roles=[{"role": "mayor", "is_unique": False, "aliases": []}])
    state = _make_config(roles=[{"role": "mayor", "is_unique": True, "aliases": ["the mayor"]}])
    result = merge_role_configs(base, state)
    mayor = next(e for e in result.roles if e.role == "mayor")
    assert mayor.is_unique is True
    assert mayor.aliases == ["the mayor"]


def test_merge_role_configs_include_false_removes_role_from_active():
    base = _make_config(roles=[{"role": "city manager"}, {"role": "mayor"}])
    override = _make_config(roles=[{"role": "city manager", "include": False}])
    result = merge_role_configs(base, override)
    active_names = {e.role.lower() for e in result.roles if e.include}
    assert "city manager" not in active_names
    assert "mayor" in active_names


def test_merge_role_configs_lower_layer_can_reenable():
    base = _make_config(roles=[{"role": "city manager", "include": False}])
    locality = _make_config(roles=[{"role": "city manager", "include": True}])
    result = merge_role_configs(base, locality)
    city_manager = next(e for e in result.roles if e.role == "city manager")
    assert city_manager.include is True


def test_merge_role_configs_empty_configs():
    result = merge_role_configs()
    assert result.roles == []


def test_merge_role_configs_single_config():
    cfg = _make_config(roles=[{"role": "mayor"}, {"role": "city manager", "include": False}])
    result = merge_role_configs(cfg)
    assert len(result.roles) == 2
    assert result.roles[0].role == "mayor"


# --- load_role_config_for_jurisdiction ---

OCDID = "ocd-jurisdiction/country:us/state:mi/place:detroit/government"


def test_load_role_config_merges_all_levels():
    responses = {
        "data_source/local/config.yml": "roles:\n  - role: mayor\n",
        "data_source/mi/config.yml": "roles:\n  - role: supervisor\n",
        "data_source/mi/local/config.yml": "roles:\n  - role: trustee\n",
    }

    def fetch(path):
        return responses.get(path)

    result = load_role_config_for_jurisdiction(OCDID, fetch)
    role_names = {e.role.lower() for e in result.roles}
    assert "mayor" in role_names
    assert "supervisor" in role_names
    assert "trustee" in role_names


def test_load_role_config_skips_missing_levels():
    responses = {
        "data_source/local/config.yml": "roles:\n  - role: mayor\n",
    }

    def fetch(path):
        return responses.get(path)

    result = load_role_config_for_jurisdiction(OCDID, fetch)
    role_names = {e.role.lower() for e in result.roles}
    assert role_names == {"mayor"}


def test_load_role_config_locality_overrides_base():
    responses = {
        "data_source/local/config.yml": "roles:\n  - role: mayor\n    is_unique: false\n",
        "data_source/mi/local/place_detroit/config.yml": "roles:\n  - role: mayor\n    is_unique: true\n",
    }

    def fetch(path):
        return responses.get(path)

    result = load_role_config_for_jurisdiction(OCDID, fetch)
    mayor = next(e for e in result.roles if e.role == "mayor")
    assert mayor.is_unique is True


def test_load_role_config_returns_empty_when_no_files_found():
    result = load_role_config_for_jurisdiction(OCDID, lambda path: None)
    assert result.roles == []


def test_load_role_config_applies_include_false_from_state_level():
    responses = {
        "data_source/local/config.yml": "roles:\n  - role: mayor\n  - role: city manager\n",
        "data_source/mi/config.yml": "roles:\n  - role: city manager\n    include: false\n",
    }

    def fetch(path):
        return responses.get(path)

    result = load_role_config_for_jurisdiction(OCDID, fetch)
    active_names = {e.role.lower() for e in result.roles if e.include}
    assert "city manager" not in active_names
    assert "mayor" in active_names
