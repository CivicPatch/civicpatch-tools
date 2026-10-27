import logging
from decimal import Decimal

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


from services.people_collector import (
    _identities,
    _log_run_summary,
    handle_submit_pipeline_run_artifacts,
)
from schemas.pipeline_runs import HandleSubmitPipelineRunArtifactsRequest, ServerDetail
from shared.schemas import Person
from shared.utils.statuses import PipelineRunStatus


def make_request(**kwargs):
    defaults = dict(
        pipeline_run_id="test-request-id",
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
        # The status and the issue both go on the run. This claimed the *changeset* until
        # migration 186: the issue was filed against whatever the run had minted, falling back
        # to the run only when it had minted nothing — which is how one table came to hold two
        # kinds of id, and why an issue from a run that died before ingest matched no changeset
        # and so vanished from every state-filtered view of the issues page.
        assert mock_upsert_issue.await_args.args[0] == "test-request-id"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_failure_before_ingest_is_not_a_special_case():
    """It used to be: no changeset meant falling back to the run id. Now every failure is keyed
    the same way, and the jurisdiction comes off the run rather than off what it proposed."""
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
    ):
        with pytest.raises(Exception, match="died before ingest"):
            await handle_submit_pipeline_run_artifacts(request)

        assert mock_upsert_issue.await_args.args[0] == "test-request-id"


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
        "services.roster_ingest.matcher_pool",
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
        "services.roster_ingest.matcher_pool",
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
        "services.roster_ingest.matcher_pool",
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


# --- the run summary Grafana reads ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_submitted_run_logs_its_summary_with_its_cap(caplog):
    request = make_request(
        jurisdiction_ocdid="ocd-jurisdiction/country:us/state:vt/place:essex/government",
        pipeline_run_status=PipelineRunStatus.SUCCESS,
    )
    costs = [{"cost_usd": 0.02, "finish_reason": "length"}]
    context = {"data": {"frontier": {"links": {}}, "stop_reason": "cost_cap_reached"}}
    with (
        patch(
            "services.people_collector.get_pipeline_run",
            new_callable=AsyncMock,
            return_value={"pipeline_run_cap_usd": Decimal("0.19")},
        ),
        caplog.at_level(logging.INFO, logger="services.people_collector"),
    ):
        await _log_run_summary(request, costs, context)

    lines = [record.getMessage() for record in caplog.records if record.getMessage().startswith("pipeline_run_finished")]
    assert len(lines) == 1
    assert " state=vt status=SUCCESS cost_usd=0.02 cap_usd=0.19 calls=1 calls_cut_at_the_output_cap=1" in lines[0]
    assert lines[0].endswith(" stop_reason=cost_cap_reached")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_summary_that_cannot_be_built_is_logged_and_does_not_raise(caplog):
    with (
        patch("services.people_collector.get_pipeline_run", new_callable=AsyncMock, side_effect=RuntimeError("db down")),
        caplog.at_level(logging.ERROR, logger="services.people_collector"),
    ):
        await _log_run_summary(make_request(), [], {})

    assert any("Failed to log the run summary" in record.getMessage() for record in caplog.records)
