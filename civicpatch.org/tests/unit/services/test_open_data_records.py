"""The shape open-data receives.

`open_data_records` round-trips the roster through `OpenStatesPersonRecord`, which means the
model — not the projection — decides what lands in the published file. That is the point, and
it is also the risk: a key `PERSON_JSON` grows and the model does not declare is dropped here
silently. These tests fail when the two drift, which is the only warning there would be.

The expected keys are written out rather than derived from the SQL: a test that computes its
expectation from the thing under test cannot disagree with it.
"""

import pytest

from services.publish import open_data_records

# `database.people.PERSON_JSON`, key for key.
_PERSON_KEYS = {
    "id",
    "name",
    "other_names",
    "phones",
    "emails",
    "urls",
    "source_urls",
    "image",
    "cdn_image",
    "start_date",
    "end_date",
    "jurisdiction_ocdid",
    "updated_at",
    "labels",
    "division_ocdid",
    "memberships",
}

# `database.people.PERSON_MEMBERSHIPS`, key for key. Ten, not eleven: `post_label` is composed
# on read and is deliberately not part of the published record.
_MEMBERSHIP_KEYS = {
    "post_id",
    "role_id",
    "role_label",
    "division_ocdid",
    "label",
    "source_labels",
    "designations",
    "unmatched_text",
    "start_date",
    "end_date",
}


def _projected() -> dict:
    """One roster row exactly as `PERSON_JSON` builds it."""
    return {
        "id": "p1",
        "name": "Ann Lee",
        "other_names": ["A. Lee"],
        "phones": ["(206) 684-4000"],
        "emails": ["ann@example.gov"],
        "urls": ["https://example.gov/ann"],
        "source_urls": ["https://example.gov/council"],
        "image": None,
        "cdn_image": None,
        "start_date": "2024",
        "end_date": None,
        "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:wa/place:zz/government",
        "updated_at": "2026-09-02T00:00:00+00:00",
        "labels": ["Mayor"],
        "division_ocdid": "ocd-division/country:us/state:wa/place:zz",
        "memberships": [
            {
                "post_id": "post-1",
                "role_id": "mayor",
                "role_label": "Mayor",
                "division_ocdid": "ocd-division/country:us/state:wa/place:zz",
                "label": "Mayor",
                "source_labels": ["Mayor"],
                "designations": [],
                "unmatched_text": [],
                "start_date": "2024",
                "end_date": None,
            }
        ],
    }


@pytest.mark.unit
def test_the_published_record_carries_every_projected_key():
    """A key the projection grows and the model does not would vanish from open-data."""
    [record] = open_data_records([_projected()])

    assert set(record) == _PERSON_KEYS


@pytest.mark.unit
def test_a_membership_carries_every_projected_key_and_no_more():
    """`post_label` is the one to watch: `Membership` has it, so dumping through that model
    instead would add a null key to every membership in every published file."""
    [record] = open_data_records([_projected()])

    assert set(record["memberships"][0]) == _MEMBERSHIP_KEYS


@pytest.mark.unit
def test_values_survive_the_round_trip():
    """Parity of keys is not enough — the values have to arrive too."""
    [record] = open_data_records([_projected()])

    assert record["name"] == "Ann Lee"
    assert record["labels"] == ["Mayor"]
    assert record["memberships"][0]["post_id"] == "post-1"
    assert record["start_date"] == "2024"


@pytest.mark.unit
def test_a_reviewers_pick_is_not_published():
    """`post_id` is a roster-document field. It has no meaning to open-data, and the model is
    what keeps it out of the file."""
    [record] = open_data_records([{**_projected(), "post_id": "post-9"}])

    assert "post_id" not in record


@pytest.mark.unit
def test_a_person_with_two_seats_keeps_both():
    """The published record is not flat — a second membership is not silently the first."""
    projected = _projected()
    second = {**projected["memberships"][0], "post_id": "post-2", "role_id": "clerk"}
    projected["memberships"] = [projected["memberships"][0], second]

    [record] = open_data_records([projected])

    assert [m["post_id"] for m in record["memberships"]] == ["post-1", "post-2"]
