import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from shared.utils.statuses import PullRequestStatus, SourceRepo
import yaml

from services.jurisdiction_pull_request import (
    _extract_state,
    merge_jurisdiction_pr,
    open_jurisdiction_edit_pr,
    open_jurisdiction_url_pr,
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


# ── open_jurisdiction_url_pr ──────────────────────────────────────────────────

OPEN_DATA_CONTENT = yaml.dump({"jurisdictions": YAML_ENTRIES}, sort_keys=False, allow_unicode=True)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_open_jurisdiction_url_pr_patches_url_and_records_change_log():
    with (
        patch(
            "services.jurisdiction_pull_request.github_service.get_github_file_contents",
            new_callable=AsyncMock,
            return_value=OPEN_DATA_CONTENT,
        ),
        patch(
            "services.jurisdiction_pull_request.open_attributed_pr",
            new_callable=AsyncMock,
            return_value=(42, "https://github.com/CivicPatch/open-data/pull/42"),
        ) as mock_open_pr,
        patch(
            "services.jurisdiction_pull_request.change_logs.record_jurisdiction_edit",
            new_callable=AsyncMock,
        ) as mock_record,
        patch(
            "services.jurisdiction_pull_request.requests_db.register_jurisdiction_edit_request",
            new_callable=AsyncMock,
        ) as mock_register,
    ):
        pr_number, pr_url, request_id = await open_jurisdiction_url_pr(
            jurisdiction_ocdid=JURISDICTION_OCDID,
            url="https://new.example.com",
            author=AUTHOR,
            user_id="user-1",
        )

    assert pr_number == 42
    # Tracked like any other PR, under the id the branch was named for.
    assert mock_register.await_args.kwargs["request_id"] == request_id
    call_kwargs = mock_open_pr.call_args.kwargs
    assert call_kwargs["file_path"] == "data_source/tx/local/jurisdictions.yml"
    # open-data is the default repo: no explicit repo_url / fork_repo_url passed
    assert "repo_url" not in call_kwargs
    assert "fork_repo_url" not in call_kwargs
    doc = yaml.safe_load(call_kwargs["content"])
    assert doc["jurisdictions"][0]["url"] == "https://new.example.com"

    mock_record.assert_awaited_once()
    record_kwargs = mock_record.call_args.kwargs
    assert record_kwargs["before_url"] == "https://old.example.com"
    assert record_kwargs["after_url"] == "https://new.example.com"
    assert record_kwargs["jurisdiction_name"] == "Austin"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_open_jurisdiction_url_pr_skips_change_log_when_url_unchanged():
    with (
        patch(
            "services.jurisdiction_pull_request.github_service.get_github_file_contents",
            new_callable=AsyncMock,
            return_value=OPEN_DATA_CONTENT,
        ),
        patch(
            "services.jurisdiction_pull_request.open_attributed_pr",
            new_callable=AsyncMock,
            return_value=(42, "https://github.com/CivicPatch/open-data/pull/42"),
        ),
        patch(
            "services.jurisdiction_pull_request.change_logs.record_jurisdiction_edit",
            new_callable=AsyncMock,
        ) as mock_record,
        patch(
            "services.jurisdiction_pull_request.requests_db.register_jurisdiction_edit_request",
            new_callable=AsyncMock,
        ) as mock_register,
    ):
        await open_jurisdiction_url_pr(
            jurisdiction_ocdid=JURISDICTION_OCDID,
            url="https://old.example.com",
            author=AUTHOR,
            user_id="user-1",
        )

    mock_record.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_open_jurisdiction_url_pr_jurisdiction_not_found():
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
            "services.jurisdiction_pull_request.open_attributed_pr",
            new_callable=AsyncMock,
        ) as mock_open_pr,
    ):
        pr_number, error, _request_id = await open_jurisdiction_url_pr(
            jurisdiction_ocdid=JURISDICTION_OCDID,
            url="https://new.example.com",
            author=AUTHOR,
            user_id="user-1",
        )

    assert pr_number is None
    assert JURISDICTION_OCDID in error
    mock_open_pr.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_open_jurisdiction_url_pr_fetch_fails():
    with patch(
        "services.jurisdiction_pull_request.github_service.get_github_file_contents",
        new_callable=AsyncMock,
        return_value=None,
    ):
        pr_number, error, _request_id = await open_jurisdiction_url_pr(
            jurisdiction_ocdid=JURISDICTION_OCDID,
            url="https://new.example.com",
            author=AUTHOR,
            user_id="user-1",
        )

    assert pr_number is None
    assert "Failed to fetch" in error


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

    mock_merge.assert_awaited_once_with(
        "42", approved_by="approver@example.com", source_repo=SourceRepo.JURISDICTIONS
    )
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
