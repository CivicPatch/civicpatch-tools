import pytest
from shared.schemas import Membership, Person, Role, RoleConfig
from shared.utils.taxonomy import build_taxonomy

from core.roster_comparison_run import build_comparison, rejected_rows
from schemas.roster_comparisons import PersonOutcome, RejectedReason, RosterComparisonUpload

TAXONOMY = build_taxonomy(RoleConfig(roles=[Role(id="member", label="Member")]))
_BARRE = "ocd-jurisdiction/country:us/state:vt/place:barre/government"
_STOWE = "ocd-jurisdiction/country:us/state:vt/place:stowe/government"
_RUTLAND = "ocd-jurisdiction/country:us/state:vt/place:rutland/government"
_NOWHERE = "ocd-jurisdiction/country:us/state:vt/place:nowhere/government"
_KEENE = "ocd-jurisdiction/country:us/state:nh/place:keene/government"


def _person(person_id: str, name: str, ocdid: str, organization_ids: tuple[str, ...] = ()) -> Person:
    members = [
        Membership(
            post_id=f"p-{person_id}-{organization_id}",
            organization_id=organization_id,
            role_id="member",
            role_label="Member",
            division_ocdid="d",
        )
        for organization_id in organization_ids or ("",)
    ]
    return Person(id=person_id, name=name, jurisdiction_ocdid=ocdid, memberships=members)


def _upload(rows: list[tuple[int, str, str]]) -> RosterComparisonUpload:
    return RosterComparisonUpload(
        state="vt",
        source_columns={"name": ["Official"]},
        corrections=[],
        rows=[{"source_row": row, "jurisdiction_ocdid": ocdid, "name": name} for row, ocdid, name in rows],
    )


@pytest.mark.unit
def test_rows_are_compared_per_jurisdiction_and_the_state_totals_add_up():
    upload = _upload([(2, _BARRE, "Jane Doe"), (3, _STOWE, "Lee Park"), (4, _BARRE, "Pat Lin")])
    rosters = {_BARRE: [_person("jane", "Jane Doe", _BARRE)], _STOWE: []}

    run = build_comparison(upload, {_BARRE, _STOWE, _RUTLAND}, rosters, TAXONOMY, {})

    assert [j.jurisdiction_ocdid for j in run.jurisdictions] == [_BARRE, _STOWE]
    barre = run.jurisdictions[0]
    assert [p.outcome for p in barre.people] == [PersonOutcome.MATCHED, PersonOutcome.ONLY_IN_UPLOADED_DATA]
    assert run.rates.outcomes.matched == 1
    assert run.rates.outcomes.only_in_uploaded_data == 2
    assert run.jurisdictions_not_named == 1


@pytest.mark.unit
def test_each_civicpatch_person_carries_their_organizations_by_name():
    upload = _upload([(2, _BARRE, "Jane Doe"), (3, _BARRE, "Pat Lin")])
    jane = _person("jane", "Jane Doe", _BARRE, ("board", "listers", "board"))
    lee = _person("lee", "Lee Park", _BARRE, ("auditors",))
    names = {"board": "Selectboard", "listers": "Board of Listers", "auditors": "Town Auditors"}

    run = build_comparison(upload, {_BARRE}, {_BARRE: [jane, lee]}, TAXONOMY, names)

    by_outcome = {p.outcome: p.organizations for p in run.jurisdictions[0].people}
    assert by_outcome == {
        PersonOutcome.MATCHED: ["Selectboard", "Board of Listers"],
        PersonOutcome.ONLY_IN_UPLOADED_DATA: [],
        PersonOutcome.ONLY_IN_CIVICPATCH: ["Town Auditors"],
    }


@pytest.mark.unit
def test_rows_outside_the_known_jurisdictions_are_rejected_with_the_reason():
    upload = _upload([(2, _NOWHERE, "Jane Doe"), (3, _KEENE, "Lee Park"), (4, _BARRE, "Pat Lin")])

    rejected = rejected_rows(upload.rows, {_BARRE}, "vt")

    assert [(r.source_row, r.reason) for r in rejected] == [
        (2, RejectedReason.UNKNOWN_JURISDICTION),
        (3, RejectedReason.OUTSIDE_STATE),
    ]


@pytest.mark.unit
def test_a_state_level_ocdid_in_the_uploaded_state_is_unknown_not_outside():
    state_level = "ocd-jurisdiction/country:us/state:vt/government"
    upload = _upload([(2, state_level, "Phil Scott")])

    rejected = rejected_rows(upload.rows, {_BARRE}, "vt")

    assert [r.reason for r in rejected] == [RejectedReason.UNKNOWN_JURISDICTION]
