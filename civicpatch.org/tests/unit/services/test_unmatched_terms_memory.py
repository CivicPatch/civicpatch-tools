"""The triage list's parse memory: kept while the roles stand, forgotten when they change."""

import pytest
from shared.schemas import Role, RoleConfig, RoleStatus
from shared.utils.taxonomy import build_taxonomy

from services.unmatched_terms import _fingerprint, _remembering


def _roles(*aliases: str) -> list[Role]:
    return [
        Role(
            id="harbormaster", label="Harbor Master", status=RoleStatus.ACTIVE,
            aliases=list(aliases), priority=10, is_unique=False,
        )
    ]


@pytest.mark.unit
def test_adding_an_alias_takes_the_term_off_at_once():
    before, after = _roles(), _roles("Harbormaster")

    unmatched_before = _remembering(_fingerprint(before), build_taxonomy(RoleConfig(roles=before)))
    assert unmatched_before("Harbormaster") == ("Harbormaster",)

    unmatched_after = _remembering(_fingerprint(after), build_taxonomy(RoleConfig(roles=after)))
    assert unmatched_after("Harbormaster") == ()
