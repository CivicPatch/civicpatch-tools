from unittest.mock import AsyncMock, patch

import pytest

from services.review_proposal import review_summary_for_request


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_request_we_do_not_hold_yields_an_empty_summary():
    """The summary is computed from the jurisdiction's rosters now, so an unknown request has
    nothing to compute against — and must not 500 the card looking."""
    with patch(
        "services.review_proposal.changesets_db.get_request_jurisdiction",
        new_callable=AsyncMock,
        return_value=None,
    ):
        assert await review_summary_for_request("missing") == {}


OCDID = "ocd-jurisdiction/country:us/state:tx/place:alpha/government"


def _person(name: str, office: str = "Mayor") -> dict:
    return {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "office": {"name": office, "division_ocdid": None},
        "jurisdiction_ocdid": OCDID,
    }


def _summary_for(published: list[dict], proposed: list[dict]):
    return patch.multiple(
        "services.review_proposal",
        changesets_db=AsyncMock(get_request_jurisdiction=AsyncMock(return_value=OCDID)),
        people_db=AsyncMock(
            get_roster=AsyncMock(return_value=published)
        ),
        proposed_roster=AsyncMock(return_value=proposed),
        get_roles=AsyncMock(return_value=[]),
        _unverified_post_issues=AsyncMock(return_value=[]),
        # Seat moves come from the derivation, not from comparing two rosters, so the summary
        # reads them separately — the same seam as post issues above.
        proposals_for_requests=AsyncMock(return_value={}),
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_somebody_we_publish_and_this_scrape_missed_is_absent():
    """The baseline is the roster we publish. It used to be the pipeline's research step,
    which lived only in the workflow context — which is why the summary had to be frozen at
    ingest and could never be recomputed."""
    with _summary_for([_person("Bob Smith")], [_person("Ann Lee")]):
        summary = await review_summary_for_request("req-1")

    codes = {issue["code"] for issue in summary["issues"]}
    assert "absent_person" in codes
    assert "new_person" in codes


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_jurisdiction_we_have_never_published_raises_nothing_about_absence():
    """Nothing to be absent from, so every person is simply new."""
    with _summary_for([], [_person("Ann Lee")]):
        summary = await review_summary_for_request("req-1")

    codes = {issue["code"] for issue in summary["issues"]}
    assert "absent_person" not in codes
    assert "new_person" in codes


@pytest.mark.unit
@pytest.mark.asyncio
async def test_the_issues_are_dicts_the_card_can_render():
    """`append_post_issues` merges these with post issues, which arrive dumped — one list, one
    shape, or the card has to tell them apart."""
    with _summary_for([_person("Bob Smith")], [_person("Ann Lee")]):
        summary = await review_summary_for_request("req-1")

    assert all(isinstance(issue, dict) for issue in summary["issues"])
