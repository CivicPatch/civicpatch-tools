"""`facts_as_of` and `snapshot_times`: the loader's cut, made in Python so history loads once."""

from datetime import datetime, timedelta, timezone

import pytest

from core.projection.as_of import facts_as_of, snapshot_times
from core.projection.canonical_ids import SAME_AS
from core.projection.facts import Claim, ClaimKind, EntityType, Facts, SourceRecord

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _at(days: int) -> datetime:
    return _T0 + timedelta(days=days)


def _record(changeset_id: str, observed: int) -> SourceRecord:
    return SourceRecord(
        id=f"{changeset_id}-r",
        changeset_id=changeset_id,
        created_at=_at(observed),
        person_id="jane",
        organization_id="council",
        name="Jane Doe",
        label="Mayor",
        source_url="https://alpha.example.gov",
    )


def _claim(changeset_id: str | None, made: int, field_path: str = "name") -> Claim:
    return Claim(
        id=f"{changeset_id}-{field_path}-{made}",
        changeset_id=changeset_id,
        created_at=_at(made),
        entity_type=EntityType.PERSON,
        entity_id="jane",
        field_path=field_path,
        kind=ClaimKind.ACCEPT,
        value="x",
    )


@pytest.mark.unit
def test_a_changesets_facts_count_from_when_it_published_not_when_they_were_made():
    facts = Facts(records=(_record("scrape", observed=0),))

    assert facts_as_of(facts, {"scrape": _at(5)}, _at(4)).records == ()
    assert len(facts_as_of(facts, {"scrape": _at(5)}, _at(5)).records) == 1


@pytest.mark.unit
def test_a_claim_with_no_changeset_counts_from_when_it_was_made():
    facts = Facts(claims=(_claim(None, made=3),))

    assert facts_as_of(facts, {}, _at(2)).claims == ()
    assert len(facts_as_of(facts, {}, _at(3)).claims) == 1


@pytest.mark.unit
def test_a_merge_applies_to_every_moment():
    """A merge says who someone always was, so history shows one person throughout."""
    facts = Facts(claims=(_claim("edit", made=9, field_path=SAME_AS),))

    assert len(facts_as_of(facts, {"edit": _at(9)}, _at(0)).claims) == 1


@pytest.mark.unit
def test_a_moment_is_dated_when_its_facts_were_observed_not_when_they_published():
    """Review lag must not move a date: read on day 1, approved on day 8."""
    facts = Facts(records=(_record("scrape", observed=1),))

    assert snapshot_times(facts, {"scrape": _at(8)}) == [(_at(8), _at(1))]


@pytest.mark.unit
def test_a_date_never_goes_back():
    """Published second but observed first would close a row before it opened."""
    facts = Facts(records=(_record("first", observed=5), _record("second", observed=2)))

    assert snapshot_times(facts, {"first": _at(6), "second": _at(7)}) == [
        (_at(6), _at(5)),
        (_at(7), _at(5)),
    ]


@pytest.mark.unit
def test_a_claim_with_no_changeset_makes_no_moment_of_its_own():
    facts = Facts(records=(_record("scrape", observed=1),), claims=(_claim(None, made=3),))

    assert snapshot_times(facts, {"scrape": _at(2)}) == [(_at(2), _at(1))]
