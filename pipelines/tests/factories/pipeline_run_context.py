from typing import Any, Dict, Union

from runners.pipeline03_people_collector.schemas import (
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
    research_municipality_step: ResearchMunicipalityStep | None = None,
) -> PeopleCollectorContext:
    default_steps: dict[PeopleCollectorState, Any] = {}

    default_steps.update(steps)

    _research = default_steps.get(PeopleCollectorStep.RESEARCH_MUNICIPALITY)
    _preprocess = default_steps.get(PeopleCollectorStep.PREPROCESS_PAGE_CONTENT)
    _process = default_steps.get(PeopleCollectorStep.PROCESS_PAGE_CONTENT)

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
            or (_research if isinstance(_research, ResearchMunicipalityStep) else None)
            or ResearchMunicipalityStep(
                identities={},
                source_urls=[],
            ),
            preprocess_page_content_step=(
                _preprocess if isinstance(_preprocess, PreprocessPageContentStep) else None
            ),
            process_page_content_step=(
                _process if isinstance(_process, ProcessPageContentStep) else None
            ),
        ),
    )

