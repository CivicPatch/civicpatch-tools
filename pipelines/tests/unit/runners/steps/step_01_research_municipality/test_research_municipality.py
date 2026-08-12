import pytest
from runners.people_collector.steps.step_01_research_municipality.research_municipality import _known_roles_from_db
from shared.utils.config_utils import RoleConfig, RoleEntry
from utils.taxonomy import build_taxonomy

pytestmark = pytest.mark.unit

_ROLE_CONFIG = RoleConfig(roles=[
    RoleEntry(role="Mayor"),
    RoleEntry(role="Council Member"),
    RoleEntry(role="Council President"),
])

_TAXONOMY = build_taxonomy(_ROLE_CONFIG)


def test_known_roles_from_db_extracts_office_names():
    existing = [
        {"name": "Alice", "office": {"name": "Mayor"}},
        {"name": "Bob", "office": {"name": "Council Member"}},
    ]
    assert _known_roles_from_db(existing, _TAXONOMY) == ["Mayor", "Council Member"]


def test_known_roles_from_db_deduplicates():
    existing = [
        {"name": "Alice", "office": {"name": "Council Member"}},
        {"name": "Bob", "office": {"name": "Council Member"}},
    ]
    assert _known_roles_from_db(existing, _TAXONOMY) == ["Council Member"]


def test_known_roles_from_db_handles_missing_office():
    existing = [
        {"name": "Alice"},
        {"name": "Bob", "office": None},
        {"name": "Carol", "office": {"name": "Mayor"}},
    ]
    assert _known_roles_from_db(existing, _TAXONOMY) == ["Mayor"]


def test_known_roles_from_db_empty():
    assert _known_roles_from_db([], _TAXONOMY) == []


def test_known_roles_from_db_splits_compound_office_names():
    existing = [
        {"name": "Alice", "office": {"name": "Council President - Council Member"}},
        {"name": "Bob", "office": {"name": "Council Member - Position 8"}},
    ]
    result = _known_roles_from_db(existing, _TAXONOMY)
    assert "Council President" in result
    assert "Council Member" in result
    assert "Position 8" not in result
