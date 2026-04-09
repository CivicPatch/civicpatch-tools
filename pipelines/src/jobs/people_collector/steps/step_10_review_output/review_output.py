import utils.log_utils as log_utils
from jobs.people_collector.schemas import (
    PeopleCollectorContext,
    ReviewOutputStep,
    PipelineStatus,
)
from shared.utils import config_utils
from shared.utils.review_utils import generate_review, ReviewInputs


def review_output(context: PeopleCollectorContext) -> ReviewOutputStep:
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 10: {PipelineStatus.REVIEW_OUTPUT} Reviewing output data.")

    research_step = context.data.research_municipality_step
    research_people = [{"name": n} for n in research_step.identities] if research_step else []
    origin_source = research_step.origin_source if research_step else "google_gemini"
    officials = context.data.format_output_step.officials

    merge_step = context.data.merge_records_within_llm_step
    unrecognized_roles = (
        [{"role": r.role, "person_name": r.person_name} for r in merge_step.unrecognized_roles]
        if merge_step else []
    )

    inputs = ReviewInputs(
        identities=research_step.identities if research_step else {},
        unique_roles=config_utils.get_unique_roles(),
        unrecognized_roles=unrecognized_roles,
    )

    result = generate_review(research_people, officials, inputs, origin_source)

    logger.info(f"review_output: {len(result['issues'])} issue(s) found.")
    return ReviewOutputStep(
        issues=result["issues"],
        people_by_source=result["people_by_source"],
        origin_source=result["origin_source"],
    )
