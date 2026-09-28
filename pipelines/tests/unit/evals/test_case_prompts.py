"""Each case's exact prompt is saved per run, so the dashboard shows what the model was sent."""

import pathlib

import pytest
import yaml
from dashboard_data import read_latest_case_prompts
from eval_utils import archive_case_prompts, record_history, record_run

pytestmark = pytest.mark.unit

NO_ACCURACY: dict = {}


def _archived(evals_dir: pathlib.Path) -> set[str]:
    return {path.stem for path in (evals_dir / "_prompts").glob("*.txt")}


def test_cases_with_the_same_prompt_share_one_file(tmp_path):
    prompts = archive_case_prompts(str(tmp_path), {"a": "Town: Millbury", "b": "Town: Millbury", "c": "Town: Sutton"})

    assert prompts["a"] == prompts["b"]
    assert prompts["a"] != prompts["c"]
    assert (tmp_path / "_prompts" / f"{prompts['c']}.txt").read_text(encoding="utf-8") == "Town: Sutton"


def test_history_keeps_the_case_prompts_it_references(tmp_path):
    run = record_run(str(tmp_path), "Town: <jurisdiction, per case>\n")
    prompts = archive_case_prompts(str(tmp_path), {"a": "Town: Millbury\n"})

    record_history(str(tmp_path), "openai", run, {}, {}, accuracy=NO_ACCURACY, mismatches=None, case_prompts=prompts)

    assert _archived(tmp_path) == {run["prompt_sha256"], prompts["a"]}


def test_the_dashboard_reads_each_providers_latest_case_prompts(tmp_path):
    report = {"run": {"prompt_sha256": "template"}, "case_prompts": {"a|Select Board": "abc"}}
    (tmp_path / "openai-eval-report.yml").write_text(yaml.safe_dump(report), encoding="utf-8")
    (tmp_path / "gemini-eval-report.yml").write_text(yaml.safe_dump({"run": {}}), encoding="utf-8")

    latest = read_latest_case_prompts(tmp_path)

    assert list(latest) == ["openai"]
    assert latest["openai"].template_sha256 == "template"
    assert latest["openai"].prompts == {"a|Select Board": "abc"}
