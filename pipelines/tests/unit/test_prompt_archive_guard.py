"""`record_run` refuses to archive a prompt with un-substituted placeholders.

Twice a prompt was archived built from empty arguments, so the stored text was missing
structure every real call sends — `Page URL:` with nothing after it, and two conditional
blocks absent. The archive is the record of what produced a run's numbers, so a degraded one
is worse than none.
"""

import pathlib
import sys

import pytest

pytestmark = pytest.mark.unit

# Anchored to this file, not the working directory. As a relative path it resolved against
# cwd, so it only worked when pytest ran from `pipelines/` — CI runs from elsewhere, put a
# path that does not exist on `sys.path`, and every import here failed.
EVALS = pathlib.Path(__file__).resolve().parents[1] / "prompts" / "tests" / "evals"


@pytest.fixture(scope="module", autouse=True)
def _eval_dir_on_path():
    path = str(EVALS.resolve())
    sys.path.insert(0, path)
    yield
    sys.path.remove(path)


def test_rejects_a_label_with_no_value(tmp_path):
    from eval_utils import record_run

    with pytest.raises(ValueError, match="un-substituted placeholders"):
        record_run(str(tmp_path), "Intro text\n\n    Page URL: \n\nMore text\n")


def test_allows_a_heading_that_introduces_a_list(tmp_path):
    """`Only extract officials from:` is a real heading, not a blanked value — the next line
    carries its content."""
    from eval_utils import record_run

    run = record_run(str(tmp_path), "Only extract officials from:\n- a table\n- a directory\n")
    assert run["prompt_sha256"]


def test_allows_the_placeholder_convention(tmp_path):
    from eval_utils import record_run

    run = record_run(str(tmp_path), "    Page URL: <page url, per case>\n")
    assert (tmp_path / "_prompts" / f"{run['prompt_sha256']}.txt").exists()


def test_archives_once_per_distinct_prompt(tmp_path):
    from eval_utils import record_run

    a = record_run(str(tmp_path), "Page URL: <per case>\n")
    b = record_run(str(tmp_path), "Page URL: <per case>\n")
    assert a["prompt_sha256"] == b["prompt_sha256"]
    assert len(list((tmp_path / "_prompts").glob("*.txt"))) == 1


def test_real_prompts_pass_the_guard(tmp_path):
    """The guard is worthless if it fires on the prompts actually in use."""
    from eval_utils import record_run
    from services.google_gemini import prompts as gemini_prompts
    from services.open_router.prompts import municipality_officials_prompt, relevant_page_prompt

    record_run(str(tmp_path), municipality_officials_prompt(["<injected per case>"]))
    record_run(str(tmp_path), relevant_page_prompt("<url>", "<place>", ["<roles>"]))
    record_run(
        str(tmp_path),
        gemini_prompts.find_jurisdiction_url_prompt(
            "ocd-jurisdiction/country:us/state:mi/place:harrison/government", "Harrison city"
        ),
    )
