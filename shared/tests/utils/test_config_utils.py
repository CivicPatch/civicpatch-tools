import pytest
from shared.utils.config_utils import RoleConfig, RoleEntry, merge_role_configs, load_role_config_for_jurisdiction


def _make_config(roles=None, excluded_roles=None) -> RoleConfig:
    return RoleConfig(
        roles=[RoleEntry(**r) for r in (roles or [])],
        excluded_roles=excluded_roles or [],
    )


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


def test_merge_role_configs_excluded_roles_removes_role():
    base = _make_config(roles=[{"role": "city manager"}, {"role": "mayor"}])
    override = _make_config(excluded_roles=["city manager"])
    result = merge_role_configs(base, override)
    role_names = {e.role.lower() for e in result.roles}
    assert "city manager" not in role_names
    assert "mayor" in role_names


def test_merge_role_configs_excluded_roles_accumulate():
    base = _make_config(excluded_roles=["city manager"])
    state = _make_config(excluded_roles=["city attorney"])
    result = merge_role_configs(base, state)
    assert "city manager" in result.excluded_roles
    assert "city attorney" in result.excluded_roles


def test_merge_role_configs_empty_configs():
    result = merge_role_configs()
    assert result.roles == []
    assert result.excluded_roles == []


def test_merge_role_configs_single_config():
    cfg = _make_config(roles=[{"role": "mayor"}], excluded_roles=["city manager"])
    result = merge_role_configs(cfg)
    assert len(result.roles) == 1
    assert result.roles[0].role == "mayor"


# --- load_role_config_for_jurisdiction ---

OCDID = "ocd-jurisdiction/country:us/state:mi/place:detroit/government"


def test_load_role_config_merges_all_levels():
    responses = {
        "data/local/config.yml": "roles:\n  - role: mayor\n",
        "data/mi/config.yml": "roles:\n  - role: supervisor\n",
        "data/mi/local/config.yml": "roles:\n  - role: trustee\n",
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
        "data/local/config.yml": "roles:\n  - role: mayor\n",
        # no state, no state+type, no locality
    }

    def fetch(path):
        return responses.get(path)

    result = load_role_config_for_jurisdiction(OCDID, fetch)
    role_names = {e.role.lower() for e in result.roles}
    assert role_names == {"mayor"}


def test_load_role_config_locality_overrides_base():
    # OCDID mi/place:detroit → folder mi/local/place_detroit (no county)
    responses = {
        "data/local/config.yml": "roles:\n  - role: mayor\n    is_unique: false\n",
        "data/mi/local/place_detroit/config.yml": "roles:\n  - role: mayor\n    is_unique: true\n",
    }

    def fetch(path):
        return responses.get(path)

    result = load_role_config_for_jurisdiction(OCDID, fetch)
    mayor = next(e for e in result.roles if e.role == "mayor")
    assert mayor.is_unique is True


def test_load_role_config_returns_empty_when_no_files_found():
    result = load_role_config_for_jurisdiction(OCDID, lambda path: None)
    assert result.roles == []
    assert result.excluded_roles == []


def test_load_role_config_applies_exclusion_from_state_level():
    responses = {
        "data/local/config.yml": "roles:\n  - role: mayor\n  - role: city manager\n",
        "data/mi/config.yml": "excluded_roles:\n  - city manager\n",
    }

    def fetch(path):
        return responses.get(path)

    result = load_role_config_for_jurisdiction(OCDID, fetch)
    role_names = {e.role.lower() for e in result.roles}
    assert "city manager" not in role_names
    assert "mayor" in role_names
