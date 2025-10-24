import os
from github_service import get_github_file_contents, get_open_pull_requests

#def test_get_github_file_contents_live():
#    github_token = os.getenv("GITHUB_WORKFLOW_TOKEN")
#    github_file_path = "data_source/co/jurisdictions.yml"  # Use a real file path that exists in the repo
#
#    assert github_token, "Set GITHUB_WORKFLOW_TOKEN in your environment"
#    content = get_github_file_contents(github_token, github_file_path)
#    assert content is not None
#    assert isinstance(content, str)
#    assert len(content) > 0

def test_get_open_pull_requests_live():
    github_token = os.getenv("GITHUB_WORKFLOW_TOKEN")

    assert github_token, "Set GITHUB_WORKFLOW_TOKEN in your environment"
    pull_requests = get_open_pull_requests(github_token)
    assert pull_requests is not None
    assert isinstance(pull_requests, list)