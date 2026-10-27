"""One finished scrape as the log line Grafana reads: cost, calls, calls cut at the output cap,
pages read, why it stopped."""

from decimal import Decimal

import pytest

from core.pipeline_run_summary import pipeline_run_summary, summary_log_line

pytestmark = pytest.mark.unit


def _context(links: dict, stop_reason: str | None) -> dict:
    return {"data": {"frontier": {"links": links}, "stop_reason": stop_reason}}


def _link(url: str, page_hash: str | None) -> dict:
    return {"url": url, "status": "processed", "page_hash": page_hash}


def test_a_run_sums_its_calls_counts_the_cut_ones_and_the_pages_it_read():
    costs = [
        {"cost_usd": 0.0012, "finish_reason": "stop"},
        {"cost_usd": 0.005, "finish_reason": "length"},
        {"cost_usd": None, "finish_reason": "stop"},
    ]
    context = _context(
        {"a": _link("https://x.gov/", "h1"), "b": _link("https://x.gov/clerk", "h2"), "c": _link("https://x.gov/gone", None)},
        "cost_cap_reached",
    )

    summary = pipeline_run_summary(costs, context)

    assert summary.cost_usd == Decimal("0.0062")
    assert (summary.calls, summary.calls_cut_at_the_output_cap, summary.pages_read) == (3, 1, 2)
    assert summary.stop_reason == "cost_cap_reached"


def test_a_run_that_wrote_no_context_or_costs_is_zero_not_an_error():
    summary = pipeline_run_summary([], {})

    assert (summary.cost_usd, summary.calls, summary.pages_read, summary.stop_reason) == (Decimal(0), 0, 0, None)


def test_the_line_is_logfmt_with_the_event_first_and_a_default_cap_named():
    summary = pipeline_run_summary([{"cost_usd": 0.01, "finish_reason": "stop"}], _context({}, None))

    line = summary_log_line("run-1", "ocd-jurisdiction/country:us/state:vt/place:essex/government", "vt", "success", None, summary)

    assert line == (
        "pipeline_run_finished pipeline_run_id=run-1"
        " jurisdiction_ocdid=ocd-jurisdiction/country:us/state:vt/place:essex/government state=vt"
        " status=success cost_usd=0.01 cap_usd=default calls=1 calls_cut_at_the_output_cap=0"
        " pages_read=0 stop_reason=none"
    )
