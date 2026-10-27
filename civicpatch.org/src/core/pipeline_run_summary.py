"""What one finished scrape cost and did, as one logfmt line Grafana can count and average:
pipelines run in GitHub Actions, so their own logs never reach VictoriaLogs."""

from decimal import Decimal

from pydantic import BaseModel

from core.source_pages import frontier_links

PIPELINE_RUN_FINISHED_EVENT = "pipeline_run_finished"
# A call that spent its whole output allowance; on AtlasCloud mostly reasoning.
OUTPUT_CAP_FINISH_REASON = "length"


class PipelineRunSummary(BaseModel):
    cost_usd: Decimal
    calls: int
    calls_cut_at_the_output_cap: int
    pages_read: int
    stop_reason: str | None


def pipeline_run_summary(llm_costs: list[dict], workflow_context: dict) -> PipelineRunSummary:
    cost = Decimal(0)
    cut = 0
    for call in llm_costs:
        cost += Decimal(str(call.get("cost_usd") or 0))
        if call.get("finish_reason") == OUTPUT_CAP_FINISH_REASON:
            cut += 1
    return PipelineRunSummary(
        cost_usd=cost,
        calls=len(llm_costs),
        calls_cut_at_the_output_cap=cut,
        pages_read=len([link for link in frontier_links(workflow_context) if link.page_hash]),
        stop_reason=workflow_context.get("data", {}).get("stop_reason"),
    )


def summary_log_line(
    pipeline_run_id: str,
    jurisdiction_ocdid: str,
    state: str,
    status: str,
    cap_usd: Decimal | None,
    summary: PipelineRunSummary,
) -> str:
    """No field holds a space, so logfmt needs no quoting; an unset cap is the pipeline's default."""
    fields = {
        "pipeline_run_id": pipeline_run_id,
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "state": state,
        "status": status,
        "cost_usd": summary.cost_usd,
        "cap_usd": cap_usd if cap_usd is not None else "default",
        "calls": summary.calls,
        "calls_cut_at_the_output_cap": summary.calls_cut_at_the_output_cap,
        "pages_read": summary.pages_read,
        "stop_reason": summary.stop_reason or "none",
    }
    return PIPELINE_RUN_FINISHED_EVENT + " " + " ".join(f"{key}={value}" for key, value in fields.items())
