import database.issues as issues_db
import database.pull_requests as pull_requests_db
import lib.github.api as github_service

# TODO: replace with a real SITE_URL env var once one exists.
SITE_DOMAIN = "civicpatch.org"


class ReviewNotFoundError(Exception):
    pass


class GithubIssueCreationError(Exception):
    pass


async def report_review_issue(changeset_id: str, description: str, user_id: str, reported_by: str) -> dict:
    review = await pull_requests_db.get_pull_request_for_review(changeset_id)
    if review is None:
        raise ReviewNotFoundError(f"No pull request found for changeset_id {changeset_id}")

    jurisdiction_name = review["jurisdiction"]["name"] or review["jurisdiction"]["ocdid"]
    jurisdiction_path = review["jurisdiction"]["path"] or ""
    state_code = jurisdiction_path.split("/")[0] if jurisdiction_path else ""
    pr_url = review["pr"]["url"]

    review_url = f"https://{SITE_DOMAIN}/review/session?state={state_code}&changeset_id={changeset_id}"
    title = f"Review flag: {jurisdiction_name}"
    body_lines = [description, "", f"Reported by {reported_by}.", f"Filed from {review_url}."]
    if pr_url:
        body_lines.append(f"Reviewing {pr_url}.")
    body = "\n".join(body_lines)

    issue_number, issue_url = await github_service.create_issue(
        title=title, body=body, labels=["user-reported"]
    )
    if issue_number is None:
        raise GithubIssueCreationError(issue_url)

    issue_id = await issues_db.create_user_reported_issue(
        changeset_id=changeset_id,
        title=title,
        body=body,
        github_issue_url=issue_url,
        github_issue_number=issue_number,
        reported_by_user_id=user_id,
    )
    return {"id": issue_id, "github_issue_url": issue_url, "github_issue_number": issue_number}
