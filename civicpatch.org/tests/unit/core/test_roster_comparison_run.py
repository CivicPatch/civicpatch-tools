import pytest
from shared.schemas import Membership, Person, Role, RoleConfig
from shared.utils.taxonomy import build_taxonomy

from core.roster_comparison_run import build_comparison
from schemas.roster_comparisons import PersonOutcome, ResolvedUpload

TAXONOMY = build_taxonomy(RoleConfig(roles=[Role(id="member", label="Member")]))
_BARRE = "ocd-jurisdiction/country:us/state:vt/place:barre/government"
_STOWE = "ocd-jurisdiction/country:us/state:vt/place:stowe/government"
_RUTLAND = "ocd-jurisdiction/country:us/state:vt/place:rutland/government"


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


def _upload(rows: list[tuple[int, str, str]]) -> ResolvedUpload:
    return ResolvedUpload(
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
