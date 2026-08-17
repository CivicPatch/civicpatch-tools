import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from shared.utils.statuses import PullRequestStatus
import yaml

from services.jurisdiction_pull_request import (
    _extract_state,
    merge_jurisdiction_pr,
    open_jurisdiction_edit_pr,
    commit_jurisdiction_patch,
    EditRejection,
)
from lib.github.pull_requests import PrAuthor

REQUEST_ID = "2026-07-31-abcd"
JURISDICTION_OCDID = "ocd-jurisdiction/country:us/state:tx/place:austin/government"
AUTHOR = PrAuthor(name="Test User", email="test@example.com")
REPO_URL = "https://api.github.com/repos/openstates/jurisdictions"
MOCK_ENV = {"JURISDICTIONS_REPO_URL": REPO_URL}

YAML_ENTRIES = [
    {
        "id": JURISDICTION_OCDID,
        "name": "Austin",
        "url": "https://old.example.com",
        "population": 900000,
        "geoid": "4805000",
    }
]
YAML_CONTENT = base64.b64encode(
    yaml.dump(YAML_ENTRIES, sort_keys=False, allow_unicode=True).encode()
).decode()


# ── _extract_state ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_extract_state_parses_correctly():
    assert _extract_state("ocd-jurisdiction/country:us/state:tx/place:austin/government") == "tx"


@pytest.mark.unit
def test_extract_state_different_state():
    assert _extract_state("ocd-jurisdiction/country:us/state:wa/place:seattle/government") == "wa"


@pytest.mark.unit
def test_extract_state_raises_on_missing():
    with pytest.raises(ValueError, match="Cannot extract state"):
        _extract_state("ocd-jurisdiction/country:us/place:austin/government")


# ── open_jurisdiction_edit_pr ─────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_open_jurisdiction_edit_pr_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"content": YAML_CONTENT}

    with (
        patch(
            "services.jurisdiction_pull_request.get_jurisdictions_sync_headers",
            new_callable=AsyncMock,
            return_value={"Authorization": "Bearer sync-token"},
        ),
        patch(
            "services.jurisdiction_pull_request.environment.get_env_vars",
            return_value=MOCK_ENV,
        ),
        patch("services.jurisdiction_pull_request.httpx.AsyncClient") as mock_client_cls,
        patch(
            "services.jurisdiction_pull_request.open_attributed_pr",
            new_callable=AsyncMock,
            return_value=(42, "https://github.com/openstates/jurisdictions/pull/42"),
        ) as mock_open_pr,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        pr_number, pr_url = await open_jurisdiction_edit_pr(
            jurisdiction_ocdid=JURISDICTION_OCDID,
            fields={"url": "https://new.example.com", "population": None, "geoid": None},
            author=AUTHOR,
        )

    assert pr_number == 42
    assert "pull/42" in pr_url

    call_kwargs = mock_open_pr.call_args.kwargs
    assert call_kwargs["file_path"] == "data/tx/local/jurisdictions.yml"
    assert call_kwargs["repo_url"] == REPO_URL
    patched_entries = yaml.safe_load(call_kwargs["content"])
    assert patched_entries[0]["url"] == "https://new.example.com"
    # Fields not provided stay unchanged
    assert patched_entries[0]["population"] == 900000


@pytest.mark.unit
@pytest.mark.asyncio
async def test_open_jurisdiction_edit_pr_jurisdiction_not_found():
    entries = [{"id": "different-jurisdiction", "url": "https://example.com"}]
    content = base64.b64encode(
        yaml.dump(entries, sort_keys=False, allow_unicode=True).encode()
    ).decode()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"content": content}

    with (
        patch(
            "services.jurisdiction_pull_request.get_jurisdictions_sync_headers",
            new_callable=AsyncMock,
            return_value={"Authorization": "Bearer sync-token"},
        ),
        patch(
            "services.jurisdiction_pull_request.environment.get_env_vars",
            return_value=MOCK_ENV,
        ),
        patch("services.jurisdiction_pull_request.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        pr_number, error = await open_jurisdiction_edit_pr(
            jurisdiction_ocdid=JURISDICTION_OCDID,
            fields={"url": "https://new.example.com"},
            author=AUTHOR,
        )

    assert pr_number is None
    assert JURISDICTION_OCDID in error


@pytest.mark.unit
@pytest.mark.asyncio
async def test_open_jurisdiction_edit_pr_file_not_found_creates_new():
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"message": "Not Found"}

    with (
        patch(
            "services.jurisdiction_pull_request.get_jurisdictions_sync_headers",
            new_callable=AsyncMock,
            return_value={"Authorization": "Bearer sync-token"},
        ),
        patch(
            "services.jurisdiction_pull_request.environment.get_env_vars",
            return_value=MOCK_ENV,
        ),
        patch("services.jurisdiction_pull_request.httpx.AsyncClient") as mock_client_cls,
        patch(
            "services.jurisdiction_pull_request.open_attributed_pr",
            new_callable=AsyncMock,
            return_value=(99, "https://github.com/openstates/jurisdictions/pull/99"),
        ) as mock_open_pr,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        pr_number, pr_url = await open_jurisdiction_edit_pr(
            jurisdiction_ocdid=JURISDICTION_OCDID,
            fields={"url": "https://new.example.com"},
            author=AUTHOR,
        )

    assert pr_number == 99
    call_kwargs = mock_open_pr.call_args.kwargs
    entries = yaml.safe_load(call_kwargs["content"])
    assert len(entries) == 1
    assert entries[0]["id"] == JURISDICTION_OCDID
    assert entries[0]["url"] == "https://new.example.com"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_open_jurisdiction_edit_pr_fetch_fails():
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {"message": "Internal Server Error"}

    with (
        patch(
            "services.jurisdiction_pull_request.get_jurisdictions_sync_headers",
            new_callable=AsyncMock,
            return_value={"Authorization": "Bearer sync-token"},
        ),
        patch(
            "services.jurisdiction_pull_request.environment.get_env_vars",
            return_value=MOCK_ENV,
        ),
        patch("services.jurisdiction_pull_request.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        pr_number, error = await open_jurisdiction_edit_pr(
            jurisdiction_ocdid=JURISDICTION_OCDID,
            fields={"url": "https://new.example.com"},
            author=AUTHOR,
        )

    assert pr_number is None
    assert "Internal Server Error" in error


# ── commit_jurisdiction_patch ──────────────────────────────────────────────────
#
# The FILE is the source here, unlike people: od_sync pulls the registry from open-data, so
# the edit reads and patches the document rather than rendering one from the database. That
# is what keeps the YAML comments real files carry (36 in ca/local, 28 in wa/counties).

OPEN_DATA_CONTENT = yaml.dump({"jurisdictions": YAML_ENTRIES}, sort_keys=False, allow_unicode=True)
COMMIT_URL = "https://github.com/CivicPatch/open-data/commit/abc123"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_commit_jurisdiction_patch_commits_and_syncs_the_row():
    with (
        patch(
            "services.jurisdiction_pull_request.github_service.get_github_file_contents",
            new_callable=AsyncMock,
            return_value=OPEN_DATA_CONTENT,
        ),
        patch(
            "services.jurisdiction_pull_request.github_service.upsert_github_file",
            new_callable=AsyncMock,
            return_value=COMMIT_URL,
        ) as mock_commit,
        patch(
            "services.jurisdiction_pull_request.jurisdictions_db.patch_jurisdiction_entry",
            new_callable=AsyncMock,
        ) as mock_patch_entry,
        patch(
            "services.jurisdiction_pull_request.change_logs.record_jurisdiction_edit",
            new_callable=AsyncMock,
        ) as mock_record,
        patch(
            "services.jurisdiction_pull_request.requests_db.register_jurisdiction_edit_request",
            new_callable=AsyncMock,
        ) as mock_register,
    ):
        commit_url, _url, request_id = await commit_jurisdiction_patch(
            jurisdiction_ocdid=JURISDICTION_OCDID,
            fields={"url": "https://new.example.com"},
            user_id="user-1",
        )

    assert commit_url == COMMIT_URL
    assert mock_register.await_args.kwargs["request_id"] == request_id

    call_kwargs = mock_commit.call_args.kwargs
    assert call_kwargs["file_path"] == "data_source/tx/local/jurisdictions.yml"
    doc = yaml.safe_load(call_kwargs["content_str"])
    assert doc["jurisdictions"][0]["url"] == "https://new.example.com"

    # The row is updated too, so the page does not wait for the next od_sync to show it.
    mock_patch_entry.assert_awaited_once_with(JURISDICTION_OCDID, {"url": "https://new.example.com"})

    mock_record.assert_awaited_once()
    record_kwargs = mock_record.call_args.kwargs
    assert record_kwargs["before_url"] == "https://old.example.com"
    assert record_kwargs["after_url"] == "https://new.example.com"
    assert record_kwargs["jurisdiction_name"] == "Austin"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_commit_jurisdiction_patch_writes_nothing_when_unchanged():
    with (
        patch(
            "services.jurisdiction_pull_request.github_service.get_github_file_contents",
            new_callable=AsyncMock,
            return_value=OPEN_DATA_CONTENT,
        ),
        patch(
            "services.jurisdiction_pull_request.github_service.upsert_github_file",
            new_callable=AsyncMock,
        ) as mock_commit,
        patch(
            "services.jurisdiction_pull_request.jurisdictions_db.patch_jurisdiction_entry",
            new_callable=AsyncMock,
        ) as mock_patch_entry,
        patch(
            "services.jurisdiction_pull_request.change_logs.record_jurisdiction_edit",
            new_callable=AsyncMock,
        ) as mock_record,
    ):
        commit_url, error, _request_id = await commit_jurisdiction_patch(
            jurisdiction_ocdid=JURISDICTION_OCDID,
            fields={"url": "https://old.example.com"},
            user_id="user-1",
        )

    assert commit_url is None
    assert error == EditRejection.NO_CHANGES
    mock_commit.assert_not_called()
    mock_patch_entry.assert_not_awaited()
    mock_record.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_commit_jurisdiction_patch_jurisdiction_not_in_the_file():
    content = yaml.dump(
        {"jurisdictions": [{"id": "different-jurisdiction", "name": "Other", "url": "x"}]},
        sort_keys=False,
    )
    with (
        patch(
            "services.jurisdiction_pull_request.github_service.get_github_file_contents",
            new_callable=AsyncMock,
            return_value=content,
        ),
        patch(
            "services.jurisdiction_pull_request.github_service.upsert_github_file",
            new_callable=AsyncMock,
        ) as mock_commit,
    ):
        commit_url, error, _request_id = await commit_jurisdiction_patch(
            jurisdiction_ocdid=JURISDICTION_OCDID,
            fields={"url": "https://new.example.com"},
            user_id="user-1",
        )

    assert commit_url is None
    assert JURISDICTION_OCDID in error
    mock_commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_commit_jurisdiction_patch_fetch_fails():
    with patch(
        "services.jurisdiction_pull_request.github_service.get_github_file_contents",
        new_callable=AsyncMock,
        return_value=None,
    ):
        commit_url, error, _request_id = await commit_jurisdiction_patch(
            jurisdiction_ocdid=JURISDICTION_OCDID,
            fields={"url": "https://new.example.com"},
            user_id="user-1",
        )

    assert commit_url is None
    assert "Failed to fetch" in error


@pytest.mark.unit
@pytest.mark.asyncio
async def test_commit_jurisdiction_patch_does_not_sync_the_row_when_the_commit_fails():
    """The file is the source, so a row updated without a landed commit would be a local
    invention that the next od_sync silently reverts."""
    with (
        patch(
            "services.jurisdiction_pull_request.github_service.get_github_file_contents",
            new_callable=AsyncMock,
            return_value=OPEN_DATA_CONTENT,
        ),
        patch(
            "services.jurisdiction_pull_request.github_service.upsert_github_file",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "services.jurisdiction_pull_request.jurisdictions_db.patch_jurisdiction_entry",
            new_callable=AsyncMock,
        ) as mock_patch_entry,
    ):
        commit_url, error, _request_id = await commit_jurisdiction_patch(
            jurisdiction_ocdid=JURISDICTION_OCDID,
            fields={"url": "https://new.example.com"},
            user_id="user-1",
        )

    assert commit_url is None
    assert "Failed to commit" in error
    mock_patch_entry.assert_not_awaited()


# ── merge_jurisdiction_pr ─────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_merge_jurisdiction_pr_merges_when_clean():
    with (
        patch(
            "services.jurisdiction_pull_request.github_service.get_pull_request_mergeability",
            new_callable=AsyncMock,
            return_value="clean",
        ),
        patch(
            "services.jurisdiction_pull_request.github_service.merge_pull_request",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_merge,
        patch(
            "services.jurisdiction_pull_request.pull_request_sync.apply_pull_request_status",
            new_callable=AsyncMock,
        ) as mock_sync,
    ):
        await merge_jurisdiction_pr("42", "approver@example.com", REQUEST_ID)

    # open-data: that is where open_jurisdiction_patch_pr opened it.
    mock_merge.assert_awaited_once_with("42", approved_by="approver@example.com")
    # This path bypasses do_merge/publish_side_effects, so without this the edit
    # would only appear after the hourly od_sync.
    mock_sync.assert_awaited_once_with(REQUEST_ID, PullRequestStatus.MERGED)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_merge_jurisdiction_pr_skips_when_not_clean():
    with (
        patch(
            "services.jurisdiction_pull_request.github_service.get_pull_request_mergeability",
            new_callable=AsyncMock,
            return_value="dirty",
        ),
        patch(
            "services.jurisdiction_pull_request.github_service.merge_pull_request",
            new_callable=AsyncMock,
        ) as mock_merge,
        patch(
            "services.jurisdiction_pull_request.pull_request_sync.apply_pull_request_status",
            new_callable=AsyncMock,
        ) as mock_sync,
    ):
        await merge_jurisdiction_pr("42", "approver@example.com", REQUEST_ID)

    mock_merge.assert_not_called()
    # Nothing merged, so there is nothing new to project into the DB.
    mock_sync.assert_not_called()
