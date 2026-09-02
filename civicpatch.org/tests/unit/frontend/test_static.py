import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from frontend.static import IMMUTABLE_CACHE_CONTROL, HashedAssetStaticFiles


@pytest.fixture
def client(tmp_path):
    hashed = tmp_path / "build" / "assets"
    hashed.mkdir(parents=True)
    (hashed / "index-C7BSUw50.js").write_text("console.log(1)")

    unhashed = tmp_path / "css"
    unhashed.mkdir()
    (unhashed / "styles.css").write_text("body{}")

    app = FastAPI()
    app.mount("/frontend", HashedAssetStaticFiles(directory=tmp_path), name="frontend")
    return TestClient(app)


@pytest.mark.unit
def test_hashed_build_asset_is_immutable(client):
    response = client.get("/frontend/build/assets/index-C7BSUw50.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == IMMUTABLE_CACHE_CONTROL


@pytest.mark.unit
def test_unhashed_file_keeps_revalidating(client):
    """styles.css keeps its name across deploys, so pinning it would serve stale CSS."""
    response = client.get("/frontend/css/styles.css")

    assert response.status_code == 200
    assert "cache-control" not in response.headers
