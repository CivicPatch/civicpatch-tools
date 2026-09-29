"""The jurisdiction pull request: what the patched file says, and the pure pieces around it.

The FILE is the source, unlike people: the sync reads the registry from the jurisdictions repo,
so an edit reads and patches the document rather than rendering one from the database. GitHub
is the only thing mocked.
"""

from unittest.mock import AsyncMock, patch

import pytest
import yaml

from database.users import SYSTEM_USER_ID
from lib.github.pull_requests import PrAuthor
from schemas.common import UserRole
from services.jurisdiction_pull_request import (
    JurisdictionEdit,
    NothingToChange,
    UnknownJurisdiction,
    _open_pr,
    label_for,
    pull_request_body,
    pull_request_number,
)
from shared.schemas import GovernmentForm
from shared.utils.statuses import PullRequestLabel

JURISDICTION_OCDID = "ocd-jurisdiction/country:us/state:tx/place:austin/government"
AUTHOR = PrAuthor(name="Test User", email="test@example.com")
REPO_URL = "https://example.test/repos/CivicPatch/open-data"
FORK_URL = "https://example.test/repos/CivicPatch/jurisdictions"
ENTRY = {
    "id": JURISDICTION_OCDID,
    "name": "Austin",
    "url": "https://old.example.com",
    "population": 900000,
    "geoid": "4805000",
}


def _file(*entries: dict) -> str:
    return yaml.dump({"jurisdictions": list(entries)}, sort_keys=False)


async def _open(content: str | None, edit: JurisdictionEdit):
    with (
        patch(
            "services.jurisdiction_pull_request.environment.get_env_vars",
            return_value={"JURISDICTIONS_REPO_URL": REPO_URL, "JURISDICTIONS_FORK_REPO_URL": FORK_URL},
        ),
        patch(
            "services.jurisdiction_pull_request.github_service.get_github_file_contents",
            new_callable=AsyncMock,
            return_value=content,
        ) as mock_fetch,
        patch(
            "services.jurisdiction_pull_request.get_jurisdictions_sync_headers",
            new_callable=AsyncMock,
            return_value={"Authorization": "Bearer sync-token"},
        ),
        patch(
            "services.jurisdiction_pull_request.github_service.get_default_headers",
            new_callable=AsyncMock,
            return_value={"Authorization": "Bearer regular-token"},
        ),
        patch(
            "services.jurisdiction_pull_request.open_attributed_pr",
            new_callable=AsyncMock,
            return_value=(42, "https://example.test/pull/42"),
        ) as mock_open_pr,
    ):
        result = await _open_pr(JURISDICTION_OCDID, edit, PullRequestLabel.MAINTAINER, AUTHOR)
    assert mock_fetch.call_args.kwargs["repo_url"] == REPO_URL
    return result, mock_open_pr


def _written_entry(mock_open_pr) -> dict:
    [entry] = yaml.safe_load(mock_open_pr.call_args.kwargs["content"])["jurisdictions"]
    return entry


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_url_edit_patches_only_the_url():
    result, mock_open_pr = await _open(_file(ENTRY), JurisdictionEdit(patch={"url": "https://new.example.com"}))

    entry = _written_entry(mock_open_pr)
    assert result == (42, "https://example.test/pull/42")
    assert (entry["url"], entry["population"]) == ("https://new.example.com", 900000)
    call = mock_open_pr.call_args.kwargs
    assert call["file_path"] == "data_source/tx/local/jurisdictions.yml"
    assert call["labels"] == (PullRequestLabel.MAINTAINER,)
    # The jurisdictions bot opens the PR on the repo; the regular bot writes the fork.
    assert (call["repo_url"], call["headers"]) == (REPO_URL, {"Authorization": "Bearer sync-token"})
    assert (call["fork_repo_url"], call["fork_headers"]) == (FORK_URL, {"Authorization": "Bearer regular-token"})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_form_goes_under_extras():
    _, mock_open_pr = await _open(
        _file(ENTRY), JurisdictionEdit(patch={}, government_form=GovernmentForm.COUNCIL_MANAGER)
    )

    entry = _written_entry(mock_open_pr)
    assert entry["extras"] == {"government_form": "council_manager"}
    assert entry["url"] == "https://old.example.com"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_the_commit_names_only_the_fields_that_change():
    edit = JurisdictionEdit(patch={"url": ENTRY["url"], "geoid": "4805001"}, government_form=GovernmentForm.COMMISSION)

    _, mock_open_pr = await _open(_file(ENTRY), edit)

    assert mock_open_pr.call_args.kwargs["commit_message"] == f"Update geoid, government_form: {JURISDICTION_OCDID}"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_null_clears_a_field():
    _, mock_open_pr = await _open(_file(ENTRY), JurisdictionEdit(patch={"url": None}))

    assert _written_entry(mock_open_pr)["url"] is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_an_edit_that_changes_nothing_is_refused():
    with_form = {**ENTRY, "extras": {"government_form": "council_manager"}}
    edit = JurisdictionEdit(patch={"url": ENTRY["url"]}, government_form=GovernmentForm.COUNCIL_MANAGER)

    with pytest.raises(NothingToChange):
        await _open(_file(with_form), edit)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_jurisdiction_missing_from_its_file_is_unknown():
    with pytest.raises(UnknownJurisdiction):
        await _open(_file({"id": "someone-else"}), JurisdictionEdit(patch={"url": "https://x.gov"}))


# ── pure pieces ───────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_the_label_follows_the_author():
    assert label_for(SYSTEM_USER_ID, UserRole.ADMINS) == PullRequestLabel.SYSTEM
    assert label_for("user-1", UserRole.ADMINS) == PullRequestLabel.ADMIN
    assert label_for("user-1", UserRole.MAINTAINERS) == PullRequestLabel.MAINTAINER
    assert label_for("user-1", UserRole.CONTRIBUTORS) is None


@pytest.mark.unit
def test_the_body_lists_each_change_and_source():
    edit = JurisdictionEdit(
        patch={"url": "https://a.gov", "geoid": None},
        government_form=GovernmentForm.MAYOR_COUNCIL,
        sources=["https://a.gov/charter"],
    )

    body = pull_request_body(edit, "local")

    assert "- `url`: https://a.gov" in body
    assert "- `geoid`: (cleared)" in body
    assert "- `extras.government_form`: `mayor_council` (local)" in body
    assert "- https://a.gov/charter" in body


@pytest.mark.unit
def test_a_body_with_no_sources_says_so():
    assert "- none given" in pull_request_body(JurisdictionEdit(patch={"url": "https://a.gov"}), "local")


@pytest.mark.unit
def test_the_number_is_the_last_path_segment():
    assert pull_request_number("https://example.test/org/repo/pull/7") == 7
