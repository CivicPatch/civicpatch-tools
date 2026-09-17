import pytest

import environment


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    """Every known variable set to a fixed test value, so no unit test reads the developer's
    real environment. Set on `os.environ` rather than patching `get_env_vars`, which it reads on
    every call: a patch has to hit each module's own binding, and `from environment import
    get_env_vars` keeps one the patch never reaches."""
    for var in environment.REQUIRED_ENV_VARS + environment.OPTIONAL_ENV_VARS:
        monkeypatch.setenv(var, f"test-{var.lower()}")
