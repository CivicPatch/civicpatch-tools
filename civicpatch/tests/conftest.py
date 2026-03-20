"""Pytest configuration and fixtures for civicpatch pipeline tests."""
import os
import sys
from pathlib import Path
import pytest

# Add shared package to Python path for local testing
shared_path = Path(__file__).parent.parent.parent.parent / "shared" / "src"
if shared_path.exists() and str(shared_path) not in sys.path:
    sys.path.insert(0, str(shared_path))

# Set env vars before any module imports so module-level get_env_vars() calls succeed
import civicpatch_environment


def _make_test_env():
    env = {}
    for var in civicpatch_environment.REQUIRED_ENV_VARS + civicpatch_environment.OPTIONAL_ENV_VARS:
        if var.endswith("_URL"):
            env[var] = f"http://test-{var.lower()}"
        else:
            env[var] = f"test-{var.lower()}"
    return env


_test_env = _make_test_env()
for _var, _val in _test_env.items():
    os.environ.setdefault(_var, _val)


@pytest.fixture(autouse=True)
def patch_get_env_vars(request, monkeypatch):
    if request.node.get_closest_marker("evals") or request.node.get_closest_marker("evals_relevant"):
        yield
        return
    monkeypatch.setattr("civicpatch_environment.get_env_vars", _make_test_env)
    yield


@pytest.fixture(autouse=True)
def patch_data_source_path(tmp_path, monkeypatch):
    """Redirect data_source lookups to a temp directory so tests don't need real data."""
    data_source = tmp_path / "data_source"
    data_source.mkdir()
    monkeypatch.setattr(
        "shared.utils.data_path_utils.get_data_source_path",
        lambda: str(data_source),
    )
    yield data_source
