"""The shape open-data receives.

`open_data_records` round-trips the roster through `OpenStatesPersonRecord`, which means the
model — not the projection — decides what lands in the published file. That is the point, and
it is also the risk: a key `PERSON_JSON` grows and the model does not declare is dropped here
silently. These tests fail when the two drift, which is the only warning there would be.

The expected keys are written out rather than derived from the SQL: a test that computes its
expectation from the thing under test cannot disagree with it.
"""

import pytest

from services.publish import open_data_records as _open_data_records
from shared.schemas import RoleConfig, Role
from shared.utils.taxonomy import build_taxonomy

# Ordering is `person_sort_key`'s, which reads a taxonomy — so these need a real one.
_TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            Role(id="mayor", label="Mayor", status="active", priority=10),
            Role(id="clerk", label="Clerk", status="active", priority=40),
        ]
    )
)


def open_data_records(roster):
    return _open_data_records(roster, _TAXONOMY)

# What the published record carries. **No longer `PERSON_JSON` key for key** — the published
# shape is now a deliberate subset with one rename, so the projection growing a key is not by
# itself a reason for it to appear in open-data.
#   `memberships` → `roles`
#   dropped: `labels`, person-level `start_date` / `end_date` / `jurisdiction_ocdid`
#            (all three are per-seat now, and live inside `roles`)
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
    "updated_at",
    "roles",
}

# Schema v2. `name` is the composed post label, not the bare role. `post_id` and the raw
# source wording stay internal; `role_id` is published because it is the stable slug a consumer
# matches on.
_ROLE_KEYS = {
    "name",
    "role_id",
    "jurisdiction_ocdid",
    "division_ocdid",
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
                "priority": 10,
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
def test_the_published_record_carries_exactly_the_published_keys():
    """Was `test_the_published_record_carries_every_projected_key`, asserting the published
    record mirrored `PERSON_JSON` exactly. It no longer does, by design: `memberships` publishes
    as `roles`, and `labels` / person-level `start_date` / `end_date` are dropped. The claim
    moves from "every projected key lands" to "these keys land and no others", which still
    catches an accidental drop or addition."""
    [record] = open_data_records([_projected()])

    assert set(record) == _PERSON_KEYS


@pytest.mark.unit
def test_a_role_carries_every_published_key_and_no_more():
    """Was `test_a_membership_carries_every_projected_key_and_no_more`. Same guarantee under the
    new name, minus `label`. `post_label` is still the one to watch: `Membership` has it, so
    dumping through that model would add a null key to every role in every published file."""
    [record] = open_data_records([_projected()])

    assert set(record["roles"][0]) == _ROLE_KEYS


@pytest.mark.unit
def test_values_survive_the_round_trip():
    """Parity of keys is not enough — the values have to arrive too."""
    [record] = open_data_records([_projected()])

    assert record["name"] == "Ann Lee"
    assert record["roles"][0]["role_id"] == "mayor"
    # Dates are per-seat now: one pair on the person could only describe one of their roles.
    assert "start_date" not in record
    assert record["roles"][0]["start_date"] == "2024"


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
    second = {
        **projected["memberships"][0],
        "post_id": "post-2",
        "role_id": "clerk",
        "priority": 40,
    }
    projected["memberships"] = [projected["memberships"][0], second]

    [record] = open_data_records([projected])

    assert [r["role_id"] for r in record["roles"]] == ["mayor", "clerk"]


# ── Output order ────────────────────────────────────────────────────────
# The published file is a git diff. Anything that reorders it silently rewrites every
# jurisdiction's file, so both axes of order are pinned here rather than inherited.


@pytest.mark.unit
def test_records_are_sorted_by_name_regardless_of_input_order():
    """Callers happen to pass a `get_roster` result, which orders by name — but that is a
    query's business. Sorting at this boundary means changing an ORDER BY cannot rewrite the
    published corpus."""
    roster = [
        {**_projected(), "name": "Zoe Adams", "id": "id-z"},
        {**_projected(), "name": "Ada Baker", "id": "id-a"},
        {**_projected(), "name": "Mo Clarke", "id": "id-m"},
    ]

    assert [r["name"] for r in open_data_records(roster)] == [
        "Ada Baker",
        "Mo Clarke",
        "Zoe Adams",
    ]


@pytest.mark.unit
def test_people_sharing_a_name_are_broken_by_id():
    """Without a total order the two could swap places between commits and read as a diff."""
    roster = [
        {**_projected(), "name": "Sam Reed", "id": "id-b"},
        {**_projected(), "name": "Sam Reed", "id": "id-a"},
    ]

    assert [r["id"] for r in open_data_records(roster)] == ["id-a", "id-b"]


@pytest.mark.unit
def test_field_order_is_the_models_declaration_order():
    """Not alphabetical — the committed corpus is in declaration order, so sorting keys would
    rewrite every file. Pinned in full, because reordering `OpenStatesPersonRecord` would
    rewrite it just as silently."""
    [record] = open_data_records([_projected()])

    assert list(record) == [
        "id",
        "name",
        "other_names",
        "phones",
        "emails",
        "urls",
        "image",
        "cdn_image",
        "source_urls",
        "updated_at",
        "roles",
    ]


@pytest.mark.unit
def test_a_roles_field_order_is_pinned_too():
    [record] = open_data_records([_projected()])

    assert list(record["roles"][0]) == [
        "name",
        "role_id",
        "jurisdiction_ocdid",
        "division_ocdid",
        "start_date",
        "end_date",
    ]


@pytest.mark.unit
def test_list_values_are_sorted_so_the_same_values_render_the_same_way():
    """`core.people_edits` builds these as `kept + accepted` — stored order then assertion
    order — so accepting a value a reviewer already had could reorder the list and diff a file
    whose content did not change."""
    person = {
        **_projected(),
        "emails": ["zoe@example.gov", "ann@example.gov"],
        "phones": ["(206) 999-0000", "(206) 111-0000"],
        "urls": ["https://b.example.gov", "https://a.example.gov"],
        "other_names": ["Zed", "Abe"],
        "source_urls": ["https://z.example.gov", "https://a.example.gov"],
    }

    [record] = open_data_records([person])

    assert record["emails"] == ["ann@example.gov", "zoe@example.gov"]
    assert record["phones"] == ["(206) 111-0000", "(206) 999-0000"]
    assert record["urls"] == ["https://a.example.gov", "https://b.example.gov"]
    assert record["other_names"] == ["Abe", "Zed"]
    assert record["source_urls"] == ["https://a.example.gov", "https://z.example.gov"]


@pytest.mark.unit
def test_roles_are_sorted_regardless_of_the_order_the_query_returned():
    """Sorted at this boundary, not inherited from `PERSON_MEMBERSHIPS`'s ORDER BY — a query is
    free to change its mind, a published file is a diff. Priority leads: a mayor outranks a
    clerk whichever order the rows arrived in."""
    person = {**_projected()}
    clerk = {**person["memberships"][0], "role_id": "clerk", "priority": 40}
    person["memberships"] = [clerk, person["memberships"][0]]

    [record] = open_data_records([person])

    assert [role["role_id"] for role in record["roles"]] == ["mayor", "clerk"]
