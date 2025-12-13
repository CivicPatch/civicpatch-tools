from domain.models import (
  Person,
  Official,
  person_to_official
)

def format_output(context: PeopleCollectorContext) -> List[Official]:
    logger = utils.log_utils.get_workflow_logger(context.data.jurisdiction_id)
    logger.info(f"Step 8: {WorkflowStatus.FORMAT_OUTPUT} Formatting output data.")

    people = context.data.merge_records_across_llms_step.people

    data = [person_to_official(person) for person in people]

    return data 