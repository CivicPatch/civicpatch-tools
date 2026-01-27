from typing import Any, Dict, Union
from domain.models import Official
from jobs.people_collector.schemas import (
    PeopleCollectorData,
    PeopleCollectorContext, 
    WorkflowStatus,
    WorkflowConfig,
    ResearchMunicipalityStep,
    SearchLinksStep,
    PreprocessPageContentStep,
    ProcessPageContentStep,
    MergeRecordsWithinLLMStep,
    MergeRecordsAcrossLLMsStep,
    FormatOutputStep,
    MaybeSendToGitHubStep,
)

def workflow_context_factory(
    steps: dict[WorkflowStatus, Any],
) -> PeopleCollectorContext:
    default_steps: Dict[WorkflowStatus, Union[
        ResearchMunicipalityStep,
        SearchLinksStep,
        PreprocessPageContentStep,
        ProcessPageContentStep,
        MergeRecordsWithinLLMStep,
        MergeRecordsAcrossLLMsStep,
        FormatOutputStep,
        MaybeSendToGitHubStep]
        ] = {}

    default_steps.update(steps)

    return PeopleCollectorContext(
        request_id="random-request-id",
        current_state=WorkflowStatus.SAVE_OUTPUT,
        data=PeopleCollectorData(
            config=WorkflowConfig(
                name="Seattle",
                url="https://seattle.gov",
                government_type="mayor_council"
            ),
            links=[],
            jurisdiction_ocdid="ocd-jurisdiction/country:us/state:wa/place:seattle/government",
            research_municipality_step=default_steps.get(WorkflowStatus.RESEARCH_MUNICIPALITY),
            search_links_step=default_steps.get(WorkflowStatus.SEARCH_LINKS, SearchLinksStep()),
            preprocess_page_content_step=default_steps.get(WorkflowStatus.PREPROCESS_PAGE_CONTENT),
            process_page_content_step=default_steps.get(WorkflowStatus.PROCESS_PAGE_CONTENT),
            merge_records_within_llm_step=default_steps.get(WorkflowStatus.MERGE_RECORDS_WITHIN_LLM),
            merge_records_across_llms_step=default_steps.get(WorkflowStatus.MERGE_RECORDS_ACROSS_LLMS),
            format_output_step=default_steps.get(WorkflowStatus.FORMAT_OUTPUT),
        )
    )