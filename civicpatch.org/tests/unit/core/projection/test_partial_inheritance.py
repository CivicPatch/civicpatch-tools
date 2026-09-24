"""What partial record inheritance must answer.

A sheet import states only the cells it fills, so a blank cell keeps whatever the person's
last full record in that organization said. The walk is per person and organization, oldest
first, and a full record resets what is carried.

Which records are partial moved onto the record itself on 2026-09-24 (`SourceRecord.is_partial`),
from a `partial_changeset_ids` set beside the facts. Every claim below is unchanged; the
fixtures say `is_partial=True` where they used to name a changeset in that set.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core.projection.facts import Facts, SourceRecord
from core.projection.partial_records import INHERITED_FIELDS, with_inherited_blanks

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
_FULL = "full-changeset"
_PARTIAL = "partial-changeset"


def record(
    id: str,
    changeset_id: str,
    minutes: int,
    person: str = "alice",
    organization: str = "council",
    label: str = "",
    email: str | None = None,
) -> SourceRecord:
    return SourceRecord(
        id=id,
        changeset_id=changeset_id,
        created_at=_T + timedelta(minutes=minutes),
        person_id=person,
        organization_id=organization,
        name="Alice Ng",
        label=label,
        source_url="https://example.gov/council",
        email=email,
        is_partial=changeset_id == _PARTIAL,
    )


def inherited(facts: Facts) -> dict[str, SourceRecord]:
    return {item.id: item for item in with_inherited_blanks(facts).records}


@pytest.mark.unit
def test_a_blank_label_keeps_the_last_full_records():
    facts = Facts(
        records=(
            record("r1", _FULL, 0, label="Mayor"),
            record("r2", _PARTIAL, 1),
        ),
    )

    assert inherited(facts)["r2"].label == "Mayor"


@pytest.mark.unit
def test_a_blank_email_keeps_the_last_full_records():
    facts = Facts(
        records=(
            record("r1", _FULL, 0, email="alice@example.gov"),
            record("r2", _PARTIAL, 1),
        ),
    )

    assert inherited(facts)["r2"].email == "alice@example.gov"


@pytest.mark.unit
def test_a_filled_label_is_not_overwritten():
    facts = Facts(
        records=(
            record("r1", _FULL, 0, label="Mayor"),
            record("r2", _PARTIAL, 1, label="Clerk"),
        ),
    )

    assert inherited(facts)["r2"].label == "Clerk"


@pytest.mark.unit
def test_a_person_with_no_prior_record_keeps_the_blank():
    facts = Facts(
        records=(record("r1", _PARTIAL, 0),),
    )

    assert inherited(facts)["r1"].label == ""


@pytest.mark.unit
def test_a_full_record_resets_what_is_carried():
    facts = Facts(
        records=(
            record("r1", _PARTIAL, 0, email="alice@example.gov"),
            record("r2", _FULL, 1),
            record("r3", _PARTIAL, 2),
        ),
    )

    assert inherited(facts)["r3"].email is None


@pytest.mark.unit
def test_no_partial_records_hands_them_back_unchanged():
    facts = Facts(
        records=(
            record("r1", _FULL, 0, label="Mayor"),
            record("r2", "other-changeset", 1),
        ),
    )

    assert with_inherited_blanks(facts).records == facts.records


# Every other field on the record, and why a blank in it inherits nothing: these identify the
# record or its source rather than stating something about the person. `name` is here because a
# sheet row is matched to a person by it, so it is never blank to begin with.
_NOT_INHERITED = {
    "id",
    "changeset_id",
    "created_at",
    "person_id",
    "organization_id",
    "name",
    "source_url",
    "is_partial",
}


@pytest.mark.unit
def test_every_field_on_a_record_is_decided_one_way_or_the_other():
    """A field added to `SourceRecord` and left out of `INHERITED_FIELDS` would be clobbered by
    a sheet import's blank cell, silently and only for imports. Fail here instead: put it in one
    list or the other."""
    assert set(INHERITED_FIELDS) | _NOT_INHERITED == set(SourceRecord.model_fields)
    assert not set(INHERITED_FIELDS) & _NOT_INHERITED
