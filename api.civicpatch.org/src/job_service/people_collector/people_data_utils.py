from shared.utils import review_utils

def extract_review_data(workflow_context: dict, people: list) -> dict:
    data = workflow_context.get("data", {})
    review = review_utils.generate_review(
        research_people=data.get("research_municipality_step", {}).get("elected_officials", []),
        people_by_llm=data.get("merge_records_within_llm_step", {}).get("people_by_llm", {}),
        people=people,
        # TODO: pass in identities from the database
    )

    return review