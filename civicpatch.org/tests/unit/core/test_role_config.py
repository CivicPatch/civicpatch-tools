import pytest

from services.role_config import build_merged_response, _scope_to_ocdid
from shared.utils.config_utils import RoleConfig, RoleEntry


def _cfg(*entries):
    return RoleConfig(roles=list(entries))


# ── build_merged_response (pure scope-merge: global → state → locality) ──────


@pytest.mark.unit
def test_merge_keeps_distinct_roles_with_their_source():
    per_level = {
        "global": _cfg(RoleEntry(role="Mayor", aliases=["mayor"])),
        "state": _cfg(RoleEntry(role="Recorder", aliases=["recorder"])),
        "locality": _cfg(RoleEntry(role="Alderman", aliases=[])),
    }
    by_role = {r.role: r for r in build_merged_response(per_level).roles}
    assert set(by_role) == {"Mayor", "Recorder", "Alderman"}
    assert by_role["Mayor"].source == "global"
    assert by_role["Recorder"].source == "state"
    assert by_role["Alderman"].source == "locality"


@pytest.mark.unit
def test_locality_overrides_global_for_same_role():
    per_level = {
        "global": _cfg(RoleEntry(role="Mayor", aliases=["mayor"], is_unique=False)),
        "locality": _cfg(RoleEntry(role="Mayor", aliases=["da mayor"], is_unique=True)),
    }
    merged = build_merged_response(per_level)
    assert len(merged.roles) == 1
    assert merged.roles[0].source == "locality"
    assert merged.roles[0].is_unique is True
    assert merged.roles[0].aliases == ["da mayor"]


@pytest.mark.unit
def test_precedence_locality_over_state_over_global():
    per_level = {
        "global": _cfg(RoleEntry(role="Clerk", aliases=["g"])),
        "state": _cfg(RoleEntry(role="Clerk", aliases=["s"])),
        "locality": _cfg(RoleEntry(role="Clerk", aliases=["l"])),
    }
    merged = build_merged_response(per_level)
    assert len(merged.roles) == 1
    assert merged.roles[0].source == "locality"
    assert merged.roles[0].aliases == ["l"]


@pytest.mark.unit
def test_merge_dedups_case_insensitively():
    per_level = {
        "global": _cfg(RoleEntry(role="Mayor", aliases=[])),
        "locality": _cfg(RoleEntry(role="mayor", aliases=[])),  # different case, same role
    }
    merged = build_merged_response(per_level)
    assert len(merged.roles) == 1
    assert merged.roles[0].source == "locality"


@pytest.mark.unit
def test_merge_tolerates_missing_levels():
    merged = build_merged_response({"global": _cfg(RoleEntry(role="Mayor", aliases=[]))})
    assert [r.role for r in merged.roles] == ["Mayor"]


@pytest.mark.unit
def test_merge_empty_is_empty():
    assert build_merged_response({}).roles == []


# ── _scope_to_ocdid (pure scope → DB ocdid mapping) ─────────────────────────


@pytest.mark.unit
def test_scope_global_maps_to_none():
    assert _scope_to_ocdid("global", "ocd-jurisdiction/country:us/state:tx/place:austin") is None


@pytest.mark.unit
def test_scope_state_appends_jurisdiction_type():
    """State-scope OCDID must end in the jurisdiction_type suffix so it parses
    as a valid state-level OCDID (vs the truncated prefix we used initially)."""
    full = "ocd-jurisdiction/country:us/state:tx/place:austin/government"
    assert _scope_to_ocdid("state", full) == "ocd-jurisdiction/country:us/state:tx/government"


@pytest.mark.unit
def test_scope_locality_maps_to_full_ocdid():
    full = "ocd-jurisdiction/country:us/state:tx/place:austin/government"
    assert _scope_to_ocdid("locality", full) == full
