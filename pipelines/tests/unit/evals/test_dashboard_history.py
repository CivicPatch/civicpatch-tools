"""The dashboard's history logic: prompt diffing and per-case change detection.

Pure functions over data, so they are unit-testable without running an eval — which
matters, because the only way to exercise them from real data is to change a prompt and
pay for two LLM runs.
"""


import pytest
import yaml
from dashboard_detail import case_movement, case_stability, prompt_diff
from eval_records import HistoryRun
from eval_utils import (
    HISTORY_DEPTH,
    _dispositions,
    _keep_recent,
    _prune_prompt_archive,
    _prune_provider_reports,
    record_history,
)

pytestmark = pytest.mark.unit


OLD_PROMPT = "line one\nKeep a link only if it matches.\nline three\n"
NEW_PROMPT = "line one\nYou MUST include every link.\nline three\n"


def test_prompt_diff_counts_only_real_changes():
    diff = prompt_diff(OLD_PROMPT, NEW_PROMPT)
    # The ---/+++ headers would otherwise be counted as changes.
    assert [line.text for line in diff if line.kind == "added"] == ["+You MUST include every link."]
    assert [line.text for line in diff if line.kind == "removed"] == ["-Keep a link only if it matches."]


def test_prompt_diff_empty_when_a_version_is_missing():
    assert prompt_diff(OLD_PROMPT, "") == []


def _runs(*cases_by_hour):
    return [HistoryRun(timestamp=f"2026-08-15T1{hour}:00:00", cases=cases) for hour, cases in enumerate(cases_by_hour)]


def test_case_movement_splits_regressions_from_improvements():
    movement = case_movement("Atlas", _runs({"a": 1.0, "b": 1.0, "c": 0.0}, {"a": 1.0, "b": 0.0, "c": 1.0}))
    assert movement is not None
    assert movement.regressed == ["b"]
    assert movement.improved == ["c"]


def test_case_movement_needs_two_runs():
    assert case_movement("Atlas", _runs({"a": 1.0})) is None


def test_case_movement_is_empty_when_nothing_moved():
    movement = case_movement("Atlas", _runs({"a": 1.0}, {"a": 1.0}))
    assert movement is not None
    assert movement.regressed == [] and movement.improved == []


def test_case_movement_ignores_cases_absent_from_the_earlier_run():
    """A newly added case has nothing to compare against and must not read as a regression."""

    movement = case_movement("Atlas", _runs({"a": 1.0}, {"a": 1.0, "brand_new": 0.0}))
    assert movement is not None
    assert movement.regressed == [] and movement.improved == []


def test_a_case_that_changed_once_is_marked_as_moving():
    assert case_stability(_runs({"a": 1.0, "b": 1.0}, {"a": 1.0, "b": 0.0}, {"a": 1.0, "b": 0.0})) == {
        "a": "steady",
        "b": "moves",
    }


# --- prompt archive pruning ---
#
# Deleting files, so the guards matter more than the happy path.


def _history(tmp_path, *shas):
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
    _archive(tmp_path, "live01", "dead01", "dead02")
    runs = [{"provider": "p", "prompt_sha256": "live01"}]
    _prune_prompt_archive(str(tmp_path), runs)
    assert _remaining(tmp_path) == ["live01"]


def test_prune_keeps_every_referenced_archive(tmp_path):
    """History spans providers and prompt versions — all of them are still diffable."""

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

    _archive(tmp_path, "aaa111")
    _prune_prompt_archive(str(tmp_path), [])
    assert _remaining(tmp_path) == ["aaa111"]


def test_prune_survives_a_missing_archive_directory(tmp_path):
    _prune_prompt_archive(str(tmp_path), [{"prompt_sha256": "aaa111"}])


def _reports(tmp_path, *providers):
    for provider in providers:
        (tmp_path / f"{provider}-eval-report.yml").write_text("accuracy: {}", encoding="utf-8")


def _report_names(tmp_path):
    return sorted(p.name.removesuffix("-eval-report.yml") for p in tmp_path.glob("*-eval-report.yml"))


def test_prune_drops_reports_for_providers_no_longer_compared(tmp_path):
    _reports(tmp_path, "open_router-AtlasCloud", "open_router-DeepInfra")
    _prune_provider_reports(str(tmp_path), {"open_router-AtlasCloud"})
    assert _report_names(tmp_path) == ["open_router-AtlasCloud"]


def test_prune_keeps_a_provider_that_failed_this_run(tmp_path):
    """It still participates — erasing its last good numbers because one run errored would
    lose the only record of what it scored."""

    _reports(tmp_path, "open_router-AtlasCloud", "open_router-DigitalOcean")
    _prune_provider_reports(str(tmp_path), {"open_router-AtlasCloud", "open_router-DigitalOcean"})
    assert _report_names(tmp_path) == ["open_router-AtlasCloud", "open_router-DigitalOcean"]


def test_prune_does_nothing_when_no_provider_participated(tmp_path):
    _reports(tmp_path, "open_router-AtlasCloud")
    _prune_provider_reports(str(tmp_path), set())
    assert _report_names(tmp_path) == ["open_router-AtlasCloud"]


def _run(model, provider, timestamp):
    return {"model": model, "provider": provider, "timestamp": timestamp}


def _lineages(runs):
    return [(r.get("model"), r["provider"], r["timestamp"]) for r in runs]


def test_keep_recent_evicts_the_oldest_run_of_the_same_lineage():
    runs = [_run("v4", "Atlas", "1"), _run("v4", "Atlas", "2")]
    kept = _keep_recent(runs, _run("v4", "Atlas", "3"), depth=2)
    assert _lineages(kept) == [("v4", "Atlas", "2"), ("v4", "Atlas", "3")]


def test_keep_recent_does_not_evict_a_retired_model():
    runs = [_run("v4", "Atlas", "1"), _run("v4", "Atlas", "2")]
    kept = _keep_recent(runs, _run("v5", "Atlas", "3"), depth=2)
    assert _lineages(kept) == [
        ("v4", "Atlas", "1"),
        ("v4", "Atlas", "2"),
        ("v5", "Atlas", "3"),
    ]


def test_keep_recent_separates_the_same_model_on_two_providers():
    runs = [_run("v4", "Atlas", "1")]
    kept = _keep_recent(runs, _run("v4", "DigitalOcean", "2"), depth=1)
    assert _lineages(kept) == [("v4", "Atlas", "1"), ("v4", "DigitalOcean", "2")]


def test_dispositions_keeps_counts_and_drops_derived_rates():
    accuracy = {
        "roles": {"correct": 7, "missing": 1, "spurious": 2, "wrong": 0,
                  "precision": 0.77, "recall": 0.87, "f1": 0.82},
    }
    assert _dispositions(accuracy) == {"roles": {"correct": 7, "missing": 1, "spurious": 2, "wrong": 0}}


def _record(tmp_path, timestamp, provider, mismatches):
    record_history(
        str(tmp_path),
        provider,
        {"timestamp": timestamp, "prompt_sha256": "aaa111"},
        {"roles": 1.0},
        {"model": "v4"},
        accuracy={},
        mismatches=mismatches,
    )


def _history_rows(tmp_path):
    return yaml.safe_load((tmp_path / "history.yml").read_text(encoding="utf-8"))["runs"]


def _run_files(tmp_path):
    return sorted(p.name for p in (tmp_path / "_runs").glob("*.yml"))


def test_mismatches_are_archived_per_run_and_referenced_from_history(tmp_path):
    rows = {"coleman_council": [{"person": "A", "field": "phone", "expected": "1", "actual": "2"}]}
    _record(tmp_path, "2026-09-16T03:49:09+00:00", "Atlas", rows)

    [row] = _history_rows(tmp_path)
    assert row["mismatches_file"] == "_runs/20260916T034909Z-Atlas.yml"
    archived = yaml.safe_load((tmp_path / row["mismatches_file"]).read_text(encoding="utf-8"))
    assert archived == {"mismatches": rows}


def test_a_run_with_no_mismatches_still_archives_an_empty_file(tmp_path):
    _record(tmp_path, "2026-09-16T03:49:09+00:00", "Atlas", {})
    [row] = _history_rows(tmp_path)
    assert "mismatches_file" in row


def test_an_eval_without_mismatches_writes_no_archive(tmp_path):
    _record(tmp_path, "2026-09-16T03:49:09+00:00", "gemini", None)
    [row] = _history_rows(tmp_path)
    assert "mismatches_file" not in row
    assert not (tmp_path / "_runs").exists()


def test_run_archive_is_pruned_with_the_history_row_that_referenced_it(tmp_path):
    for hour in range(HISTORY_DEPTH + 1):
        _record(tmp_path, f"2026-09-16T0{hour}:00:00+00:00", "Atlas", {})
    assert "20260916T000000Z-Atlas.yml" not in _run_files(tmp_path)
    assert len(_run_files(tmp_path)) == HISTORY_DEPTH


def test_keep_recent_treats_unstamped_history_as_its_own_lineage():
    runs = [{"provider": "Atlas", "timestamp": "1"}]
    kept = _keep_recent(runs, _run("v4", "Atlas", "2"), depth=1)
    assert _lineages(kept) == [(None, "Atlas", "1"), ("v4", "Atlas", "2")]
