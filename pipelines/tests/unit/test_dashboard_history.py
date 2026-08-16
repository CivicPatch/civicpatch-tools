"""The dashboard's history logic: prompt diffing and per-case change detection.

Pure functions over data, so they are unit-testable without running an eval — which
matters, because the only way to exercise them from real data is to change a prompt and
pay for two LLM runs.
"""

import pathlib
import sys

import pytest

pytestmark = pytest.mark.unit

EVALS = pathlib.Path("tests/prompts/tests/evals")


@pytest.fixture(scope="module", autouse=True)
def _eval_dir_on_path():
    path = str(EVALS.resolve())
    sys.path.insert(0, path)
    yield
    sys.path.remove(path)


@pytest.fixture
def archive(tmp_path):
    (tmp_path / "_prompts").mkdir()
    (tmp_path / "_prompts/old111.txt").write_text("line one\nKeep a link only if it matches.\nline three\n")
    (tmp_path / "_prompts/new222.txt").write_text("line one\nYou MUST include every link.\nline three\n")
    return tmp_path


def test_prompt_diff_counts_only_real_changes(archive):
    import visualize

    html = visualize._prompt_diff(archive, "new222", "old111")
    assert "+1" in html and "-1" in html
    # The ---/+++ headers would otherwise be counted and coloured as changes.
    assert "old111</span>" not in html
    assert "You MUST include every link." in html
    assert "Keep a link only if it matches." in html


def test_prompt_diff_empty_when_a_version_is_missing(archive):
    import visualize

    assert visualize._prompt_diff(archive, "new222", "absent") == ""


def test_case_changes_splits_regressions_from_improvements():
    import visualize

    html = visualize._case_changes([
        {"timestamp": "2026-08-15T10:00:00", "cases": {"a": 1.0, "b": 1.0, "c": 0.0}},
        {"timestamp": "2026-08-15T11:00:00", "cases": {"a": 1.0, "b": 0.0, "c": 1.0}},
    ])
    assert "regressed" in html and ">b<" not in html and " b<" in html
    assert "improved" in html and " c<" in html
    assert " a<" not in html  # unchanged cases are noise here


def test_case_changes_needs_two_runs():
    import visualize

    assert visualize._case_changes([{"timestamp": "2026-08-15T10:00:00", "cases": {"a": 1.0}}]) == ""


def test_case_changes_says_so_when_nothing_moved():
    import visualize

    run = {"timestamp": "2026-08-15T10:00:00", "cases": {"a": 1.0}}
    html = visualize._case_changes([run, {**run, "timestamp": "2026-08-15T11:00:00"}])
    assert "no case changed" in html


def test_case_changes_ignores_cases_absent_from_the_earlier_run():
    """A newly added case has nothing to compare against and must not read as a regression."""
    import visualize

    html = visualize._case_changes([
        {"timestamp": "2026-08-15T10:00:00", "cases": {"a": 1.0}},
        {"timestamp": "2026-08-15T11:00:00", "cases": {"a": 1.0, "brand_new": 0.0}},
    ])
    assert "no case changed" in html


# --- prompt archive pruning ---
#
# Deleting files, so the guards matter more than the happy path.


def _history(tmp_path, *shas):
    import yaml

    (tmp_path / "history.yml").write_text(
        yaml.safe_dump({"runs": [{"provider": "p", "prompt_sha256": s} for s in shas]}),
        encoding="utf-8",
    )


def _archive(tmp_path, *shas):
    (tmp_path / "_prompts").mkdir(exist_ok=True)
    for sha in shas:
        (tmp_path / "_prompts" / f"{sha}.txt").write_text("x", encoding="utf-8")


def _remaining(tmp_path):
    return sorted(p.stem for p in (tmp_path / "_prompts").glob("*.txt"))


def test_prune_drops_archives_no_run_references(tmp_path):
    from eval_utils import _prune_prompt_archive
    import yaml

    _archive(tmp_path, "live01", "dead01", "dead02")
    runs = [{"provider": "p", "prompt_sha256": "live01"}]
    _prune_prompt_archive(str(tmp_path), runs)
    assert _remaining(tmp_path) == ["live01"]


def test_prune_keeps_every_referenced_archive(tmp_path):
    """History spans providers and prompt versions — all of them are still diffable."""
    from eval_utils import _prune_prompt_archive

    _archive(tmp_path, "aaa111", "bbb222")
    runs = [
        {"provider": "a", "prompt_sha256": "aaa111"},
        {"provider": "b", "prompt_sha256": "bbb222"},
    ]
    _prune_prompt_archive(str(tmp_path), runs)
    assert _remaining(tmp_path) == ["aaa111", "bbb222"]


def test_prune_does_nothing_on_an_empty_history(tmp_path):
    """No runs means "nothing recorded yet", not "nothing referenced" — pruning there would
    delete the prompt the current run just archived."""
    from eval_utils import _prune_prompt_archive

    _archive(tmp_path, "aaa111")
    _prune_prompt_archive(str(tmp_path), [])
    assert _remaining(tmp_path) == ["aaa111"]


def test_prune_survives_a_missing_archive_directory(tmp_path):
    from eval_utils import _prune_prompt_archive

    _prune_prompt_archive(str(tmp_path), [{"prompt_sha256": "aaa111"}])


def _reports(tmp_path, *providers):
    for provider in providers:
        (tmp_path / f"{provider}-eval-report.yml").write_text("accuracy: {}", encoding="utf-8")


def _report_names(tmp_path):
    return sorted(p.name.removesuffix("-eval-report.yml") for p in tmp_path.glob("*-eval-report.yml"))


def test_prune_drops_reports_for_providers_no_longer_compared(tmp_path):
    from eval_utils import _prune_provider_reports

    _reports(tmp_path, "open_router-AtlasCloud", "open_router-DeepInfra")
    _prune_provider_reports(str(tmp_path), {"open_router-AtlasCloud"})
    assert _report_names(tmp_path) == ["open_router-AtlasCloud"]


def test_prune_keeps_a_provider_that_failed_this_run(tmp_path):
    """It still participates — erasing its last good numbers because one run errored would
    lose the only record of what it scored."""
    from eval_utils import _prune_provider_reports

    _reports(tmp_path, "open_router-AtlasCloud", "open_router-DigitalOcean")
    _prune_provider_reports(str(tmp_path), {"open_router-AtlasCloud", "open_router-DigitalOcean"})
    assert _report_names(tmp_path) == ["open_router-AtlasCloud", "open_router-DigitalOcean"]


def test_prune_does_nothing_when_no_provider_participated(tmp_path):
    from eval_utils import _prune_provider_reports

    _reports(tmp_path, "open_router-AtlasCloud")
    _prune_provider_reports(str(tmp_path), set())
    assert _report_names(tmp_path) == ["open_router-AtlasCloud"]
