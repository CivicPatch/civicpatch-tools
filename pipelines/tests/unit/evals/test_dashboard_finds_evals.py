"""The dashboard finds an eval by its report, so a new eval needs no list to be added to: only to
write its report through `write_pass_fail_report`."""

import pathlib

import pytest
import yaml

import dashboard_data

pytestmark = pytest.mark.unit

EVALS_SOURCE = pathlib.Path(__file__).resolve().parents[2] / "prompts" / "tests" / "evals"
# F1 per field from comparison.yml: the one eval the dashboard names rather than finds.
OFFICIALS_EVAL = "test_local_municipal_officials_eval.py"


def _write_report(directory: pathlib.Path, report: dict) -> None:
    directory.mkdir(parents=True)
    (directory / f"open_router{dashboard_data.REPORT_SUFFIX}").write_text(yaml.safe_dump(report))


def test_a_folder_with_a_pass_fail_report_is_found_and_one_without_is_not(tmp_path, monkeypatch):
    _write_report(tmp_path / "new_eval", {"total_cases": 2, "passed_cases": 2, "failed_cases": []})
    _write_report(tmp_path / "old_shape", {"roles_right": 1.0})
    monkeypatch.setattr(dashboard_data, "EVALS", tmp_path)

    found = dashboard_data.eval_dirs()

    assert list(found) == [dashboard_data.OFFICIALS, "new_eval"]
    assert dashboard_data.dataset_dir("new_eval").endswith("/new_eval")


@pytest.mark.parametrize("eval_file", sorted(p.name for p in EVALS_SOURCE.glob("test_*_eval.py") if p.name != OFFICIALS_EVAL))
def test_every_eval_writes_the_report_the_dashboard_finds(eval_file):
    assert "write_pass_fail_report(" in (EVALS_SOURCE / eval_file).read_text(), (
        f"{eval_file} must write its report through eval_utils.write_pass_fail_report, or the dashboard never shows it"
    )
