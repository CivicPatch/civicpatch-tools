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
