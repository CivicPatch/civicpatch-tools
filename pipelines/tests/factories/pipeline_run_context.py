from typing import Any, Dict, Union

from runners.people_collector.schemas import (
    LinkFrontier,
    MaybeSendToGitHubStep,
    PeopleCollectorContext,
    PeopleCollectorData,
    PipelineRunConfig,
    PipelineStatus,
    PreprocessPageContentStep,
    ProcessPageContentStep,
    ResearchMunicipalityStep,
)


def pipeline_run_context_factory(
    steps: dict[PipelineStatus, Any],
    research_municipality_step=None,
) -> PeopleCollectorContext:
    default_steps: Dict[
        PipelineStatus,
        Union[
            ResearchMunicipalityStep,
            PreprocessPageContentStep,
            ProcessPageContentStep,
            MaybeSendToGitHubStep,
        ],
    ] = {}

    default_steps.update(steps)

    return PeopleCollectorContext(
        request_id="random-request-id",
        current_state=PipelineStatus.SAVE_OUTPUT,
        data=PeopleCollectorData(
            config=PipelineRunConfig(
                name="Seattle",
                url="https://seattle.gov",
            ),
            frontier=LinkFrontier(),
            jurisdiction_ocdid="ocd-jurisdiction/country:us/state:wa/place:seattle/government",
            research_municipality_step=research_municipality_step
            or default_steps.get(PipelineStatus.RESEARCH_MUNICIPALITY)
            or ResearchMunicipalityStep(
                expected_count=0,
                target_designations=[],
                known_roles=[],
                identities={},
                source_urls=[],
            ),
            preprocess_page_content_step=default_steps.get(
                PipelineStatus.PREPROCESS_PAGE_CONTENT
            ),
            process_page_content_step=default_steps.get(
                PipelineStatus.PROCESS_PAGE_CONTENT
            ),
        ),
    )
