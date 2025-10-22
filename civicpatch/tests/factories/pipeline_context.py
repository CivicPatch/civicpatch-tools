from typing import Any, Dict, Union
from schemas import (
    PipelineContext, PipelineStatus,
    ResearchMunicipalityStep,
    SearchLinksStep,
    PreprocessPageContentStep,
    ProcessPageContentStep,
    MergeRecordsWithinLLMStep,
    MergeRecordsAcrossLLMsStep,
    MaybeSendToGitHubStep,
)

def pipeline_context_factory(
    steps: dict[PipelineStatus, Any],
) -> PipelineContext:
    default_steps: Dict[PipelineStatus, Union[
        ResearchMunicipalityStep,
        SearchLinksStep,
        PreprocessPageContentStep,
        ProcessPageContentStep,
        MergeRecordsWithinLLMStep,
        MergeRecordsAcrossLLMsStep,
        MaybeSendToGitHubStep]
        ] = {
    }    

    default_steps.update(steps)

    return PipelineContext(
        request_id="random-request-id",
        name="Seattle",
        url="https://seattle.gov",
        links=[],
        jurisdiction_id="seattle_wa",
        steps=default_steps,
    )