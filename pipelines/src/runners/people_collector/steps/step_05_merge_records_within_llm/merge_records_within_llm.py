"""Step 05 — group the scrape's records into people.

The grouping itself moved to `shared.utils.reconcile` on 2026-08-21; cp.org needs it too,
and needs it working there before the pipeline stops emitting merged people. What is left
here is the step contract: unpack the context, call it, wrap the result.
"""

from runners.people_collector.schemas import (
    MergeRecordsWithinLLMStep,
    PeopleCollectorContext,
)
from shared.utils.reconcile import reconcile
from shared.utils.taxonomy import build_taxonomy
from utils import log_utils


def merge_records_within_llm(
    context: PeopleCollectorContext,
) -> MergeRecordsWithinLLMStep:
    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    assert context.data.process_page_content_step is not None, (
        "should never happen — process_page_content_step is required before merge_records_within_llm"
    )

    assert context.data.research_municipality_step is not None, (
        "should never happen — research_municipality_step is required before merge_records_within_llm"
    )

    records = [
        record
        for group in context.data.process_page_content_step.records.values()
        for record in group
    ]

    people = reconcile(
        records,
        context.data.research_municipality_step.identities,
        build_taxonomy(context.data.role_config),
        jurisdiction_ocdid,
        log_utils.get_pipeline_run_logger(jurisdiction_ocdid),
    )

    return MergeRecordsWithinLLMStep(records=people)
