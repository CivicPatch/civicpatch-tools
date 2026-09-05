import pytest
from unittest.mock import AsyncMock, patch, MagicMock


from services.people_collector import (
    _identities,
    handle_submit_pipeline_run_artifacts,
)
from schemas.pipeline_runs import HandleSubmitPipelineRunArtifactsRequest, ServerDetail
from shared.schemas import Person
from shared.utils.statuses import PipelineRunStatus


def make_request(**kwargs):
    defaults = dict(
        changeset_id="test-request-id",
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
            "services.people_collector.pipeline_run_service.apply_pipeline_run_status",
            new_callable=AsyncMock,
        ) as mock_apply_status,
        patch(
            "services.people_collector.upsert_issue",
            new_callable=AsyncMock,
        ) as mock_upsert_issue,
        patch(
            "services.people_collector.get_pipeline_run",
            new_callable=AsyncMock,
            return_value={"changeset_id": "minted-changeset-id"},
        ),
    ):
        with pytest.raises(Exception, match="storage unavailable"):
            await handle_submit_pipeline_run_artifacts(request)

        # Through the lifecycle service, not straight to the row: the direct write left the
        # run terminal while its proposal stayed in the review queue.
        mock_apply_status.assert_awaited_once_with(
            "test-request-id",
            PipelineRunStatus.ERROR,
            None,
            "ocd-division/country:us/state:ca/place:oakland",
        )
        # The status goes on the run; the issue goes on the changeset that run minted.
        # `issues.changeset_ids` is read by joining `changesets`, so a run id resolves to
        # nothing there.
        assert mock_upsert_issue.await_args.args[0] == "minted-changeset-id"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_failure_before_ingest_files_no_issue():
    """It minted no changeset, so there is nothing for the issue to hang off — and a row keyed
    on the run would join to no jurisdiction. The failed run is what records this one."""
    request = make_request()
    with (
        patch(
            "services.people_collector._handle_submit_pipeline_run_artifacts",
            new_callable=AsyncMock,
            side_effect=Exception("died before ingest"),
        ),
        patch(
            "services.people_collector.pipeline_run_service.apply_pipeline_run_status",
            new_callable=AsyncMock,
        ),
        patch(
            "services.people_collector.upsert_issue",
            new_callable=AsyncMock,
        ) as mock_upsert_issue,
        patch(
            "services.people_collector.get_pipeline_run",
            new_callable=AsyncMock,
            return_value={"changeset_id": None},
        ),
    ):
        with pytest.raises(Exception, match="died before ingest"):
            await handle_submit_pipeline_run_artifacts(request)

        mock_upsert_issue.assert_not_awaited()


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
            "services.people_collector.pipeline_run_service.apply_pipeline_run_status",
            new_callable=AsyncMock,
        ) as mock_apply_status,
    ):
        result = await handle_submit_pipeline_run_artifacts(request)

        assert result == mock_response
        mock_apply_status.assert_not_awaited()


# --- identities: the prior reconciliation groups a scrape's records against ---


def _context_with_identities(identities: dict) -> dict:
    return {"data": {"research_municipality_step": {"identities": identities}}}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_identities_come_from_cp_orgs_own_people_when_it_has_any():
    """Its own published people are the better prior — they are confirmed, and the scrape's
    research is a guess."""
    with patch(
        "services.roster_ingest.get_person_models",
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
        "services.roster_ingest.get_person_models",
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
        "services.roster_ingest.get_person_models",
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


def _official(name: str, person_id: str = "") -> dict:
    return {
        "id": person_id,
        "name": name,
        "office": {"name": "Mayor"},
        "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:zz/place:zz/government",
        "source_urls": [],
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
