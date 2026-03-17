import utils.log_utils as log_utils
from jobs.people_collector.schemas import (
    PeopleCollectorContext,
    ReviewOutputStep,
    WorkflowStatus,
)
from jobs.people_collector.steps.step_10_review_output.utils import generate_review


def review_output(context: PeopleCollectorContext) -> ReviewOutputStep:
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 10: {WorkflowStatus.REVIEW_OUTPUT} Reviewing output data.")

    research_people = (
        context.data.research_municipality_step.people
        if context.data.research_municipality_step
        else []
    )
    officials = context.data.format_output_step.officials
    identities = context.data.format_output_step.config.identities or {}

    result = generate_review(research_people, officials, identities)

    logger.info(f"review_output: {len(result['issues'])} issue(s) found.")
    return ReviewOutputStep(issues=result["issues"])
