def extract_issues(workflow_context: dict) -> list:
    data = workflow_context.get("data", {})
    review_output_step = data.get("review_output_step") or {}
    return review_output_step.get("issues", [])