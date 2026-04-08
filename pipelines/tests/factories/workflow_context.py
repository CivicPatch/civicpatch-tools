from typing import Any, Dict, Union
from domain.models import Official
from jobs.people_collector.schemas import (
    PeopleCollectorData,
    PeopleCollectorContext,
    PipelineStatus,
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
    steps: dict[PipelineStatus, Any],
    research_municipality_step=None,
) -> PeopleCollectorContext:
    default_steps: Dict[PipelineStatus, Union[
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
        current_state=PipelineStatus.SAVE_OUTPUT,
        data=PeopleCollectorData(
            config=WorkflowConfig(
                name="Seattle",
                url="https://seattle.gov",
            ),
            links=[],
            jurisdiction_ocdid="ocd-jurisdiction/country:us/state:wa/place:seattle/government",
            research_municipality_step=research_municipality_step or default_steps.get(PipelineStatus.RESEARCH_MUNICIPALITY) or ResearchMunicipalityStep(
                expected_count=0, target_designations=[], roles_hint=[], identities={}, source_urls=[]
            ),
            search_links_step=default_steps.get(PipelineStatus.SEARCH_LINKS, SearchLinksStep()),
            preprocess_page_content_step=default_steps.get(PipelineStatus.PREPROCESS_PAGE_CONTENT),
            process_page_content_step=default_steps.get(PipelineStatus.PROCESS_PAGE_CONTENT),
            merge_records_within_llm_step=default_steps.get(PipelineStatus.MERGE_RECORDS_WITHIN_LLM),
            merge_records_across_llms_step=default_steps.get(PipelineStatus.MERGE_RECORDS_ACROSS_LLMS),
            format_output_step=default_steps.get(PipelineStatus.FORMAT_OUTPUT),
        )
    )
