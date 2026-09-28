"""Candidate relevance eval cases from saved runs, labelled by open-data's published rosters.

Offline: no network, no LLM, no cost. Writes to `datasets/candidates/relevant_page/` for a person
to review and move into `datasets/local/relevant_page/`; nothing here is trusted on its own.

A page is relevant if a published person cites it in `source_urls`: that is a reviewed answer.
A page nobody cites is only *probably* irrelevant (a second roster page that was never picked
as a source looks the same), so a negative is written only where the saved run judged the page
relevant, and is marked for review. Pages both sides call irrelevant are skipped.

    uv run python -m tests.prompts.tests.evals.generate_relevance_cases --open-data ../open-data
"""

import argparse
import glob
import json
import os
import re
from enum import Enum

import yaml
from pydantic import BaseModel
from runners.people_collector.schemas import LinkStatus
from shared.utils.url_utils import canonical_url
from tests.prompts.tests.evals.eval_utils import GENERATED_KEY

DATA_SOURCE = "data_source"
DATASET = "tests/prompts/datasets/local/relevant_page"
CANDIDATES = "tests/prompts/datasets/candidates/relevant_page"

# The statuses that carry the saved run's own relevance verdict; every other status never got one.
_JUDGED_RELEVANT = {LinkStatus.DONE.value, LinkStatus.PROCESSED_HEURISTICS_FAIL.value}
_JUDGED_IRRELEVANT = {LinkStatus.PROCESSED_IRRELEVANT.value}


# --- What the stages pass along ---


class SavedPage(BaseModel):
    url: str
    status: str
    input_path: str


class SavedRun(BaseModel):
    folder: str
    jurisdiction_ocdid: str
    jurisdiction_name: str
    pages: list[SavedPage]


class Candidate(Enum):
    RELEVANT = "relevant"
    RELEVANT_MODEL_DISAGREED = "relevant, the saved run said irrelevant"
    IRRELEVANT_TO_REVIEW = "irrelevant by absence, the saved run said relevant"


class CandidateCase(BaseModel):
    case_id: str
    page_url: str
    jurisdiction_name: str
    candidate: Candidate
    input_path: str


# --- Reading ---


def read_saved_runs() -> list[SavedRun]:
    """Every saved run, keeping only pages whose preprocessed content was saved."""
    runs = []
    for context_path in glob.glob(os.path.join(DATA_SOURCE, "*", "*", "*", "pipeline_run_context.json")):
        run_dir = os.path.dirname(context_path)
        with open(context_path) as f:
            data = json.load(f)["data"]
        pages = []
        for link in data.get("frontier", {}).get("links", {}).values():
            input_path = os.path.join(run_dir, "cache", link.get("folder_name") or "", "preprocessed.md")
            if link.get("folder_name") and os.path.exists(input_path):
                pages.append(SavedPage(url=link["url"], status=link["status"], input_path=input_path))
        runs.append(
            SavedRun(
                folder=os.path.basename(run_dir),
                jurisdiction_ocdid=data["jurisdiction_ocdid"],
                jurisdiction_name=data["config"].get("name") or "",
                pages=pages,
            )
        )
    return runs


def read_cited_urls(open_data: str) -> dict[str, set[str]]:
    """Every published person's `source_urls`, canonical, under each jurisdiction they hold a role in."""
    cited: dict[str, set[str]] = {}
    for path in glob.glob(os.path.join(open_data, "data", "**", "*.yml"), recursive=True):
        with open(path) as f:
            people = yaml.safe_load(f) or []
        for person in people:
            urls = {canonical_url(url) for url in person.get("source_urls") or []}
            for role in person.get("roles") or []:
                cited.setdefault(role["jurisdiction_ocdid"], set()).update(urls)
    return cited


def read_dataset_page_urls() -> set[str]:
    """Pages already in the dataset, so they are not proposed twice."""
    urls = set()
    for path in glob.glob(os.path.join(DATASET, "*", "expected.yml")):
        with open(path) as f:
            urls.add(canonical_url(yaml.safe_load(f)["page_url"]))
    return urls


# --- Deciding (pure) ---


def candidate_for(status: str, cited: bool) -> Candidate | None:
    """None when the saved run gave no verdict, or when both sides call the page irrelevant."""
    if status not in _JUDGED_RELEVANT and status not in _JUDGED_IRRELEVANT:
        return None
    if cited and status in _JUDGED_IRRELEVANT:
        return Candidate.RELEVANT_MODEL_DISAGREED
    if cited:
        return Candidate.RELEVANT
    if status in _JUDGED_RELEVANT:
        return Candidate.IRRELEVANT_TO_REVIEW
    return None


def case_id(run_folder: str, input_path: str) -> str:
    page_folder = os.path.basename(os.path.dirname(input_path))
    return re.sub(r"[^a-z0-9_-]", "_", f"{run_folder}__{page_folder}".lower())


def candidate_cases(run: SavedRun, cited: set[str], known: set[str]) -> list[CandidateCase]:
    """This run's pages worth a case. A run whose jurisdiction has no published roster has none."""
    if not cited:
        return []
    cases = []
    for page in run.pages:
        if canonical_url(page.url) in known:
            continue
        candidate = candidate_for(page.status, canonical_url(page.url) in cited)
        if candidate is None:
            continue
        cases.append(
            CandidateCase(
                case_id=case_id(run.folder, page.input_path),
                page_url=page.url,
                jurisdiction_name=run.jurisdiction_name,
                candidate=candidate,
                input_path=page.input_path,
            )
        )
    return cases


def expected_yaml(case: CandidateCase) -> str:
    thoughts = f"GENERATED, review before moving into the dataset: {case.candidate.value}."
    if case.candidate is Candidate.IRRELEVANT_TO_REVIEW:
        thoughts += " Nobody published cites this page, which is weak evidence it is irrelevant."
    is_relevant = case.candidate is not Candidate.IRRELEVANT_TO_REVIEW
    return yaml.safe_dump(
        {
            "page_url": case.page_url,
            "jurisdiction_name": case.jurisdiction_name,
            GENERATED_KEY: True,
            "page": {"is_relevant": is_relevant, "relevant_urls": [], "thoughts": thoughts},
        },
        sort_keys=False,
    )


# --- Writing ---


def write_case(case: CandidateCase) -> None:
    case_dir = os.path.join(CANDIDATES, case.case_id)
    os.makedirs(case_dir, exist_ok=True)
    with open(case.input_path) as source, open(os.path.join(case_dir, "input.md"), "w") as target:
        target.write(source.read())
    with open(os.path.join(case_dir, "expected.yml"), "w") as f:
        f.write(expected_yaml(case))


# --- Entry point ---


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--open-data", required=True, help="path to the open-data repo checkout")
    open_data = parser.parse_args().open_data

    runs = read_saved_runs()
    cited = read_cited_urls(open_data)
    known = read_dataset_page_urls()

    cases = []
    for run in runs:
        cases.extend(candidate_cases(run, cited.get(run.jurisdiction_ocdid, set()), known))

    for case in cases:
        write_case(case)

    for candidate in Candidate:
        count = len([case for case in cases if case.candidate is candidate])
        print(f"{count:4d}  {candidate.value}")
    print(f"written to {CANDIDATES}")


if __name__ == "__main__":
    main()
