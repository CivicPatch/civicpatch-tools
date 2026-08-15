import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def pytest_sessionfinish(session, exitstatus):
    """Refresh the dashboard after any eval run.

    Only fires when this directory's conftest was loaded — i.e. when evals were actually
    collected — so the unit-test loop never touches it. Runs on failure too: a red run is
    exactly when you want to look at the numbers.

    Never fails the session. The evals cost real money, and losing a completed run because
    the reporting step raised would be a worse outcome than a stale dashboard.
    """
    import visualize

    try:
        rows = visualize.write_dashboard()
    except Exception as exc:  # noqa: BLE001 — reported, not swallowed; see docstring
        print(f"\n[dashboard] not regenerated: {exc!r}", flush=True)
        return
    if rows:
        print(f"\n[dashboard] {visualize.OUTPUT} updated ({rows} rows)", flush=True)
