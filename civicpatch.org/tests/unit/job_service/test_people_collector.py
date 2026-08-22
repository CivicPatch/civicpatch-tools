import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import json

from services.people_collector import (
    _identities,
    _read_image_map,
    _review_summary,
    handle_submit_pipeline_run_artifacts,
)
from schemas.pipeline_runs import HandleSubmitPipelineRunArtifactsRequest, ServerDetail
from shared.schemas import Person
from shared.utils.statuses import PipelineRunStatus


def make_request(**kwargs):
    defaults = dict(
        request_id="test-request-id",
        jurisdiction_ocdid="ocd-division/country:us/state:ca/place:oakland",
        server_detail=ServerDetail(user_email="test@civicpatch.org", server_url="civicpatch.org"),
        zip_path="/tmp/test.zip",
        temp_dir="/tmp/test",
        pipeline_run_status="ERROR",
    )
    return HandleSubmitPipelineRunArtifactsRequest(**{**defaults, **kwargs})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_submit_pipeline_run_artifacts_updates_status_to_error_on_failure():
    request = make_request()
    with (
        patch(
            "services.people_collector._handle_submit_pipeline_run_artifacts",
            new_callable=AsyncMock,
            side_effect=Exception("storage unavailable"),
        ),
        patch(
            "services.people_collector.update_pipeline_run_status",
            new_callable=AsyncMock,
        ) as mock_update_status,
        patch(
            "services.people_collector.upsert_issue",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(Exception, match="storage unavailable"):
            await handle_submit_pipeline_run_artifacts(request)

        mock_update_status.assert_awaited_once_with(
            "test-request-id", status=PipelineRunStatus.ERROR, progress=None
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_submit_pipeline_run_artifacts_does_not_update_status_on_success():
    request = make_request()
    mock_response = MagicMock()
    with (
        patch(
            "services.people_collector._handle_submit_pipeline_run_artifacts",
            new_callable=AsyncMock,
            return_value=mock_response,
        ),
        patch(
            "services.people_collector.update_pipeline_run_status",
            new_callable=AsyncMock,
        ) as mock_update_status,
    ):
        result = await handle_submit_pipeline_run_artifacts(request)

        assert result == mock_response
        mock_update_status.assert_not_awaited()


# --- identities: the prior reconciliation groups a scrape's records against ---


def _context_with_identities(identities: dict) -> dict:
    return {"data": {"research_municipality_step": {"identities": identities}}}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_identities_come_from_cp_orgs_own_people_when_it_has_any():
    """Its own published people are the better prior — they are confirmed, and the scrape's
    research is a guess."""
    with patch(
        "services.people_collector.get_people_for_jurisdiction",
        new_callable=AsyncMock,
        return_value=[Person(name="Ann Lee", other_names=["A. Lee"], jurisdiction_ocdid="x")],
    ):
        assert await _identities("x", _context_with_identities({"Bob": []})) == {
            "Ann Lee": ["A. Lee"]
        }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_identities_fall_back_to_the_scrapes_own_research():
    """A jurisdiction cp.org has never published has nobody to compare against, which is
    exactly when the pipeline's research is worth reading."""
    with patch(
        "services.people_collector.get_people_for_jurisdiction",
        new_callable=AsyncMock,
        return_value=[],
    ):
        assert await _identities("x", _context_with_identities({"Bob": ["Bobby"]})) == {
            "Bob": ["Bobby"]
        }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_prior_at_all_is_not_an_error():
    """Grouping falls back to fuzzy matching on the records alone."""
    with patch(
        "services.people_collector.get_people_for_jurisdiction",
        new_callable=AsyncMock,
        return_value=[],
    ):
        assert await _identities("x", {}) == {}


# --- review summary: computed at ingest, not received ---


def _context_with_research(identities: dict) -> dict:
    return {
        "data": {
            "research_municipality_step": {
                "identities": identities,
                "origin_source": "existing",
            }
        }
    }


def _official(name: str) -> dict:
    return {
        "name": name,
        "office": {"name": "Mayor"},
        "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:zz/place:zz/government",
        "source_urls": [],
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_the_review_summary_is_json_serialisable():
    """It goes straight to `json.dumps`. The pipeline never had to think about this — it
    returned issues inside a step model that serialised on the way out."""
    with patch(
        "services.people_collector.get_roles", new_callable=AsyncMock, return_value=[]
    ):
        summary = await _review_summary(
            [_official("Ann Lee")], _context_with_research({"Bob Smith": []})
        )

    json.dumps(summary)
    assert all(isinstance(issue, dict) for issue in summary["issues"])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_somebody_the_run_looked_for_and_did_not_find_is_an_issue():
    with patch(
        "services.people_collector.get_roles", new_callable=AsyncMock, return_value=[]
    ):
        summary = await _review_summary(
            [_official("Ann Lee")], _context_with_research({"Bob Smith": []})
        )

    codes = {issue["code"] for issue in summary["issues"]}
    assert "absent_official" in codes
    assert "new_official" in codes


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_run_with_no_research_prior_raises_nothing_about_absence():
    """Absence is measured against what the run set out to look for. With no prior there is
    nothing to be absent from — every person is simply new."""
    with patch(
        "services.people_collector.get_roles", new_callable=AsyncMock, return_value=[]
    ):
        summary = await _review_summary([_official("Ann Lee")], {})

    codes = {issue["code"] for issue in summary["issues"]}
    assert "absent_official" not in codes


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_failed_review_summary_does_not_fail_the_submit():
    """The people are already stored by this point. A scrape must not be marked errored over
    the summary describing them — received as JSON this could not fail, computed it can."""
    with patch(
        "services.people_collector.get_roles",
        new_callable=AsyncMock,
        side_effect=Exception("roles unavailable"),
    ):
        assert await _review_summary([_official("Ann Lee")], {}) == {}


# --- the image map, read out of the zip ---


@pytest.mark.unit
def test_no_image_map_is_not_an_error(tmp_path):
    """A run that found no photos ships no map. Provenance is simply unknown then."""
    assert _read_image_map(str(tmp_path)) == {}


@pytest.mark.unit
def test_the_image_map_is_found_where_the_zip_puts_it(tmp_path):
    """Under `images/`, which is why it arrives at all — the image pattern sweeps that
    directory, so the map ships beside the files it describes."""
    images = tmp_path / "data_source" / "wa" / "local" / "buckley" / "images"
    images.mkdir(parents=True)
    (images / "image_map.json").write_text('{"ann.png": "https://alpha.gov/ann.png"}')

    assert _read_image_map(str(tmp_path)) == {"ann.png": "https://alpha.gov/ann.png"}
