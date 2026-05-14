import pytest
from unittest.mock import patch, MagicMock

import lib.storage as storage_service


@pytest.fixture(autouse=True)
def _reset_module_state():
    storage_service._url_cache.clear()
    storage_service._logged_storage_missing = False
    yield
    storage_service._url_cache.clear()
    storage_service._logged_storage_missing = False


@pytest.mark.unit
def test_get_presigned_url_cached_returns_none_when_storage_unconfigured():
    with patch("lib.storage.get_client", side_effect=ValueError("missing env")):
        result = storage_service.get_presigned_url_cached("civicpatch-debug", "some/key")
    assert result is None


@pytest.mark.unit
def test_get_presigned_url_cached_logs_only_once_when_unconfigured(caplog):
    with patch("lib.storage.get_client", side_effect=ValueError("missing env")):
        storage_service.get_presigned_url_cached("civicpatch-debug", "k1")
        storage_service.get_presigned_url_cached("civicpatch-debug", "k2")
        storage_service.get_presigned_url_cached("civicpatch-debug", "k3")

    warnings = [r for r in caplog.records if r.levelname == "WARNING" and "Storage client unavailable" in r.message]
    assert len(warnings) == 1


@pytest.mark.unit
def test_get_presigned_url_cached_returns_url_when_configured():
    fake_client = MagicMock()
    fake_client.generate_presigned_url.return_value = "https://signed.example/x"
    with patch("lib.storage.get_client", return_value=fake_client):
        result = storage_service.get_presigned_url_cached("bucket", "key")
    assert result == "https://signed.example/x"
