"""`claims_for_edit`: the derived roster and what the client says, in; claims out.

Pure, so no mocks. This is the whole decision the edit route makes — everything around it is
loading the roster, minting a changeset and publishing.
"""

import pytest

from core.people_edits import POSTS_FIELD, PeopleValidationError
from schemas.claims import ClaimKind
from schemas.jurisdictions import PersonEdit, OfficeEdit
from services.jurisdiction_edits import claims_for_edit, membership_label_edits

MAYOR = "11111111-1111-5111-8111-111111111111"
CLERK = "22222222-2222-5222-8222-222222222222"
CHANGESET = "c1"
OCDID = "ocd-jurisdiction/country:us/state:tx/place:alpha/government"


def _derived(**overrides) -> dict[str, dict]:
    person = {
        "id": "p1",
        "name": "Ann Lee",
        "emails": ["ann@example.gov"],
        "phones": [],
        # `display_rows` fills these, and validation requires them: a person needs a jurisdiction
        # and somewhere they were seen.
        "jurisdiction_ocdid": OCDID,
        "source_urls": ["https://alpha.gov/council"],
        "updated_at": None,
        "memberships": [{"post_id": MAYOR, "label": "Mayor"}],
        **overrides,
    }
    return {person["id"]: person}


def _pairs(claims):
    return [(claim.field_path, claim.kind, claim.value) for claim in claims]


@pytest.mark.unit
def test_saying_what_already_stands_files_nothing():
    """The editor sends every person on the screen. A save that changed nothing must leave no
    trace, or the audit trail fills with claims nobody made."""
    edit = PersonEdit(
        id="p1", fields={"name": "Ann Lee"}, offices=[OfficeEdit(id=MAYOR, membership_label="Mayor")]
    )

    assert claims_for_edit(_derived(), [edit], CHANGESET) == []


@pytest.mark.unit
def test_a_changed_field_accepts_the_new_value():
    edit = PersonEdit(id="p1", fields={"name": "Ann Lee-Park"})

    assert _pairs(claims_for_edit(_derived(), [edit], CHANGESET)) == [
        ("name", ClaimKind.ACCEPT, "Ann Lee-Park")
    ]


@pytest.mark.unit
def test_clearing_a_field_rejects_what_was_there():
    """The reject is what makes the fold answer None: there is no "unset" claim."""
    edit = PersonEdit(id="p1", fields={"name": ""})

    assert _pairs(claims_for_edit(_derived(), [edit], CHANGESET)) == [
        ("name", ClaimKind.REJECT, "Ann Lee")
    ]


@pytest.mark.unit
def test_absent_posts_says_nothing_about_them():
    """`posts` absent is "this edit does not touch their posts", which is not the same as `[]`."""
    edit = PersonEdit(id="p1", fields={"name": "Ann Lee-Park"})

    assert not [claim for claim in claims_for_edit(_derived(), [edit], CHANGESET)
                if claim.field_path == POSTS_FIELD]


@pytest.mark.unit
def test_an_empty_posts_list_removes_them_from_the_roster():
    edit = PersonEdit(id="p1", offices=[])

    assert _pairs(claims_for_edit(_derived(), [edit], CHANGESET)) == [
        (POSTS_FIELD, ClaimKind.REJECT, MAYOR)
    ]


@pytest.mark.unit
def test_a_move_is_an_accept_and_a_reject():
    edit = PersonEdit(id="p1", offices=[OfficeEdit(id=CLERK)])

    assert _pairs(claims_for_edit(_derived(), [edit], CHANGESET)) == [
        (POSTS_FIELD, ClaimKind.ACCEPT, CLERK),
        (POSTS_FIELD, ClaimKind.REJECT, MAYOR),
    ]


@pytest.mark.unit
def test_somebody_the_roster_does_not_derive_is_an_addition():
    """Nothing to diff against, so every field they carry is an accept, and the post they are
    given is one too. `roster.py` clusters them on the `name` accept."""
    edit = PersonEdit(
        id="p2",
        fields={
            "name": "Bo Nguyen",
            "jurisdiction_ocdid": OCDID,
            "source_urls": ["https://alpha.gov/council"],
        },
        offices=[OfficeEdit(id=CLERK)],
    )

    assert _pairs(claims_for_edit(_derived(), [edit], CHANGESET)) == [
        ("name", ClaimKind.ACCEPT, "Bo Nguyen"),
        (POSTS_FIELD, ClaimKind.ACCEPT, CLERK),
    ]


@pytest.mark.unit
def test_every_claim_is_filed_under_the_one_changeset():
    """One edit is one changeset, because undoing it is rolling that changeset back."""
    edits = [
        PersonEdit(id="p1", fields={"name": "Ann Lee-Park"}, offices=[OfficeEdit(id=CLERK)]),
        PersonEdit(
            id="p2",
            fields={
                "name": "Bo Nguyen",
                "jurisdiction_ocdid": OCDID,
                "source_urls": ["https://alpha.gov/council"],
            },
        ),
    ]

    claims = claims_for_edit(_derived(), edits, CHANGESET)

    assert claims
    assert all(claim.changeset_id == CHANGESET for claim in claims)


@pytest.mark.unit
def test_a_renamed_seat_is_a_membership_label_change():
    """What a person's seat is called, not what the post is called: the post's own name is a
    maintainer's act on the posts route."""
    edit = PersonEdit(id="p1", offices=[OfficeEdit(id=MAYOR, membership_label="Acting Mayor")])

    assert [label for _, label in membership_label_edits(_derived(), [edit])] == ["Acting Mayor"]


@pytest.mark.unit
def test_an_unchanged_seat_name_changes_nothing():
    edit = PersonEdit(id="p1", offices=[OfficeEdit(id=MAYOR, membership_label="Mayor")])

    assert membership_label_edits(_derived(), [edit]) == []


@pytest.mark.unit
def test_clearing_a_seat_name_asks_for_the_derived_guess_back():
    """`None` is a withdrawal, which is why labels are not claims here: a withdrawal names a
    row, not a value."""
    edit = PersonEdit(id="p1", offices=[OfficeEdit(id=MAYOR, membership_label=None)])

    assert [label for _, label in membership_label_edits(_derived(), [edit])] == [None]


@pytest.mark.unit
def test_a_seat_name_is_keyed_on_the_person_and_the_post():
    from shared.utils.membership_ids import membership_id

    edit = PersonEdit(id="p1", offices=[OfficeEdit(id=MAYOR, membership_label="Acting Mayor")])

    assert [entity for entity, _ in membership_label_edits(_derived(), [edit])] == [
        membership_id("p1", MAYOR)
    ]


# Moved here 2026-09-23 from tests/unit/routers/test_review.py, where the same claims were made
# of `POST /{changeset_id}/save` through four mocked loaders. The rule is pure, so it is tested
# where it lives. Each kept its sentence.


@pytest.mark.unit
def test_reformatting_a_number_the_scrape_already_found_claims_nothing():
    """The reviewer retypes `9168085300`; the roster already has `(916) 808-5300`. Normalizing
    makes them the same value, so there is nothing for a human to have claimed — a save must
    not manufacture a claim out of a formatting difference."""
    derived = _derived(phones=["(916) 808-5300"])
    edit = PersonEdit(id="p1", fields={"phones": ["9168085300"]})

    assert claims_for_edit(derived, [edit], CHANGESET) == []


@pytest.mark.unit
def test_an_edited_field_is_recorded_canonicalized():
    """The number the reviewer typed is accepted canonicalized, and the one that was there is
    rejected."""
    derived = _derived(phones=["(916) 808-5300"])
    edit = PersonEdit(id="p1", fields={"phones": ["9165551234"]})

    claims = claims_for_edit(derived, [edit], CHANGESET)

    assert sorted((claim.kind.value, claim.value) for claim in claims) == [
        ("accept", "(916) 555-1234"),
        ("reject", "(916) 808-5300"),
    ]
    assert {claim.field_path for claim in claims} == {"phones"}


@pytest.mark.unit
def test_an_invalid_field_is_refused_rather_than_claimed():
    """Validation runs before the diff, so a bad value never becomes a claim somebody has to
    roll back."""
    edit = PersonEdit(id="p1", fields={"emails": ["not-an-email"]})

    with pytest.raises(PeopleValidationError):
        claims_for_edit(_derived(), [edit], CHANGESET)


@pytest.mark.unit
def test_a_person_added_by_hand_is_claims_not_evidence():
    """Decided 2026-09-23. It used to write a source record as well, on the reasoning that a
    human is a source. One rule is simpler and outlives a scrape: a human's answer is always a
    claim, and only scrapes write source records."""
    edit = PersonEdit(
        id="p2",
        fields={
            "name": "Bo Nguyen",
            "jurisdiction_ocdid": OCDID,
            "source_urls": ["https://alpha.gov/council"],
        },
        offices=[OfficeEdit(id=CLERK)],
    )

    claims = claims_for_edit(_derived(), [edit], CHANGESET)

    assert _pairs(claims) == [
        ("name", ClaimKind.ACCEPT, "Bo Nguyen"),
        (POSTS_FIELD, ClaimKind.ACCEPT, CLERK),
    ]
