from typing import Any, Dict, Union

from runners.people_collector.schemas import (
    LinkFrontier,
    MaybeSendToGitHubStep,
    PeopleCollectorContext,
    PeopleCollectorData,
    PeopleCollectorState,
    PeopleCollectorStep,
    PipelineRunConfig,
    PreprocessPageContentStep,
    ProcessPageContentStep,
    ResearchMunicipalityStep,
)


def pipeline_run_context_factory(
    steps: dict[PeopleCollectorState, Any],
    research_municipality_step=None,
) -> PeopleCollectorContext:
    default_steps: Dict[
        PeopleCollectorState,
        Union[
            ResearchMunicipalityStep,
            PreprocessPageContentStep,
            ProcessPageContentStep,
            MaybeSendToGitHubStep,
        ],
    ] = {}

    default_steps.update(steps)

    return PeopleCollectorContext(
        pipeline_run_id="random-request-id",
        current_state=PeopleCollectorStep.SAVE_OUTPUT,
        data=PeopleCollectorData(
            config=PipelineRunConfig(
                name="Seattle",
                url="https://seattle.gov",
            ),
            frontier=LinkFrontier(),
            jurisdiction_ocdid="ocd-jurisdiction/country:us/state:wa/place:seattle/government",
            research_municipality_step=research_municipality_step
            or default_steps.get(PeopleCollectorStep.RESEARCH_MUNICIPALITY)
            or ResearchMunicipalityStep(
                identities={},
                source_urls=[],
            ),
            preprocess_page_content_step=default_steps.get(
                PeopleCollectorStep.PREPROCESS_PAGE_CONTENT
            ),
            process_page_content_step=default_steps.get(
                PeopleCollectorStep.PROCESS_PAGE_CONTENT
            ),
        ),
    )
