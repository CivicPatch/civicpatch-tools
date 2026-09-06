"""Every entrypoint imports cleanly, in a fresh interpreter.

The worker entrypoints are the only modules that pulls the whole Temporal graph — workflows import the
activities module, which imports the services it runs — and nothing else in the suite touches
it. When `services/publish.py` started importing `lib.temporal.client`, that closed a cycle and
the worker died on startup while all 626 other tests stayed green.

The subprocess is the point. Importing in-process proves nothing: by the time pytest reaches
this file, other tests have already imported `lib.temporal.client` (they patch it), so it sits
in `sys.modules` and the loop never closes. Verified by reintroducing the real cycle — the
in-process version passed, this one fails.
"""

import os
import subprocess
import sys

import pytest

# `pythonpath = ["."]` in pyproject puts the project root on the path for pytest; a fresh
# interpreter needs the same, plus src/ for the app's own top-level packages.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SRC = os.path.join(_PROJECT_ROOT, "src")


@pytest.mark.unit
@pytest.mark.parametrize(
    "module",
    [
        # The Temporal graph: workflows -> activities -> services. Where the cycle appeared.
        # One entry per worker: each is a separate process with a deliberately different
        # import graph, so a cycle can close in one and not the others.
        "workers.jurisdictions",
        "workers.sinks",
        "workers.expiry",
        # The scrape entrypoint carries the smallest graph of the four — it must not reach
        # `database` or `services` at all.
        "workers.scrape",
        # The web entrypoint, which pulls every router.
        "main",
    ],
)
def test_module_imports_in_a_clean_interpreter(module):
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([_SRC, _PROJECT_ROOT])}
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, f"importing {module} failed:\n{result.stderr}"
