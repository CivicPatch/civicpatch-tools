"""Whether every office the scrape expects has been seen, which replaced a hard-coded "Mayor"."""

import pytest

from runners.people_collector.schemas import ExpectedMembership, PersonSourceRecord
from runners.people_collector.steps.step_04_process_page_content.process_page_content import (
    found_every_expected_role,
)
from shared.schemas import Role, RoleConfig
from shared.utils.taxonomy import build_taxonomy

pytestmark = pytest.mark.unit

_TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            Role(id="mayor", label="Mayor"),
            Role(id="council-member", label="Council Member"),
            Role(id="council-president", label="Council President"),
        ]
    )
)


def _expected(*roles: str) -> list[ExpectedMembership]:
    return [ExpectedMembership(organization_id="government", role_label=role) for role in roles]


def _seen(name: str, label: str) -> list[PersonSourceRecord]:
    return [PersonSourceRecord(name=name, label=label, source_url="https://seattle.gov")]


def test_a_missing_mayor_keeps_a_complete_council_crawling():
    records = {"Rob Saka": _seen("Rob Saka", "Council Member District 1")}

    assert not found_every_expected_role(_TAXONOMY, records, _expected("Mayor", "Council Member"))


def test_every_role_seen_once_is_enough():
    """Seen, not complete: a name beside the office is all this asks."""
    records = {
        "Katie Wilson": _seen("Katie Wilson", "Mayor"),
        "Rob Saka": _seen("Rob Saka", "Council Member District 1"),
        "Joy Hollingsworth": _seen("Joy Hollingsworth", "Council President District 3"),
    }

    assert found_every_expected_role(
        _TAXONOMY, records, _expected("Mayor", "Council Member", "Council Member", "Council President")
    )


def test_a_jurisdiction_without_a_mayor_is_not_held_to_one():
    """The old rule required "Mayor" wherever the expected roles named it or named nothing."""
    records = {"Ann Lee": _seen("Ann Lee", "Council President")}

    assert found_every_expected_role(_TAXONOMY, records, _expected("Council President"))


def test_nothing_expected_asks_for_no_roles():
    assert found_every_expected_role(_TAXONOMY, {}, [])
