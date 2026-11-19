from typing import Any, Dict, Union

from runners.pipeline03_people_collector.schemas import (
    LinkFrontier,
    MaybeSendToGitHubStep,
    PeopleCollectorContext,
    PeopleCollectorData,
    PeopleCollectorState,
    PeopleCollectorStep,
    PipelineRunConfig,
    ResearchMunicipalityStep,
)


def pipeline_run_context_factory(
    steps: dict[PeopleCollectorState, Any],
    research_municipality_step: ResearchMunicipalityStep | None = None,
) -> PeopleCollectorContext:
    default_steps: dict[PeopleCollectorState, Any] = {}

    default_steps.update(steps)

    _research = default_steps.get(PeopleCollectorStep.RESEARCH_MUNICIPALITY)
    research = (
        research_municipality_step
        or (_research if isinstance(_research, ResearchMunicipalityStep) else None)
        or ResearchMunicipalityStep(
            identities={},
            source_urls=[],
        )
    )

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
            research_municipality_step=research,
        ),
    )
