import utils.log_utils as log_utils
from jobs.people_collector.schemas import (
    PeopleCollectorContext,
    ReviewOutputStep,
    WorkflowStatus,
)
from shared.utils.review_utils import generate_review


def review_output(context: PeopleCollectorContext) -> ReviewOutputStep:
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 10: {WorkflowStatus.REVIEW_OUTPUT} Reviewing output data.")

    research_step = context.data.research_municipality_step
    research_people = [{"name": n} for n in research_step.identities] if research_step else []
    origin_source = research_step.origin_source if research_step else "google_gemini"
    officials = context.data.format_output_step.officials
    identities = research_step.identities if research_step else {}

    result = generate_review(research_people, officials, identities, origin_source)

    logger.info(f"review_output: {len(result['issues'])} issue(s) found.")
    return ReviewOutputStep(
        issues=result["issues"],
        people_by_source=result["people_by_source"],
        origin_source=result["origin_source"],
    )
