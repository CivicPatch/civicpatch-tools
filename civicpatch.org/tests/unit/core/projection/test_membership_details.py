"""What a membership's own records say about it: the dates it was seen between, and the
pages and wordings behind it. What the labels carried beyond the winning role is
`test_parse_labels`, which reads them."""

from datetime import datetime, timedelta, timezone

import pytest

from shared.schemas import Role, RoleConfig, RoleStatus
from shared.utils.taxonomy import build_taxonomy

from core.projection.facts import Claim, ClaimKind, EntityType, SourceRecord
from core.projection.membership_details import (
    MembershipSource,
    first_seen,
    membership_sources,
)

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
JURISDICTION = "ocd-jurisdiction/country:us/state:tx/place:alpha/government"
COUNCIL_PAGE = "https://example.gov/council"
MAYOR_PAGE = "https://example.gov/mayor"


def _role(id_, label, priority):
    return Role(
        id=id_, label=label, status=RoleStatus.ACTIVE, aliases=[], priority=priority,
        is_unique=False,
    )


ROLES = [_role("mayor", "Mayor", 10), _role("council-member", "Council Member", 500)]
TAXONOMY = build_taxonomy(RoleConfig(roles=ROLES))


def record(
    id: str, label: str = "Mayor", minutes: int = 0, source_url: str = COUNCIL_PAGE
) -> SourceRecord:
    return SourceRecord(
        id=id,
        changeset_id=f"c-{id}",
        created_at=_T + timedelta(minutes=minutes),
        person_id="alice",
        organization_id="council",
        name="Alice Ng",
        label=label,
        source_url=source_url,
    )


def exists_accept(id: str, minutes: int = 0) -> Claim:
    return Claim(
        id=id,
        changeset_id="c9",
        created_at=_T + timedelta(minutes=minutes),
        entity_type=EntityType.MEMBERSHIP,
        entity_id="membership-alice-mayor",
        field_path="exists",
        kind=ClaimKind.ACCEPT,
        value={"organization_id": "council", "role_id": "mayor", "division_ocdid": "base"},
    )


@pytest.mark.unit
def test_seen_dates_span_the_records_whatever_order_they_arrive_in():
    """Checked both ends; `last_seen` went with its column (228), so now the start only."""
    records = [record("r2", minutes=20), record("r0", minutes=0), record("r1", minutes=10)]
    assert first_seen(records) == _T


@pytest.mark.unit
def test_a_membership_only_a_claim_holds_is_seen_when_the_claim_was_made():
    claim = exists_accept("a0", minutes=5)
    assert first_seen([claim]) == _T + timedelta(minutes=5)


@pytest.mark.unit
def test_records_and_claims_are_one_span():
    evidence = [record("r0", minutes=10), exists_accept("a0", minutes=0)]
    assert first_seen(evidence) == _T


@pytest.mark.unit
def test_sources_are_each_distinct_label_and_page_oldest_first():
    records = [
        record("r1", "Mayor", minutes=10, source_url=MAYOR_PAGE),
        record("r0", "Mayor", minutes=0),
        record("r2", "Mayor", minutes=20),
    ]
    assert membership_sources(records) == (
        MembershipSource(note="Mayor", url=COUNCIL_PAGE),
        MembershipSource(note="Mayor", url=MAYOR_PAGE),
    )
