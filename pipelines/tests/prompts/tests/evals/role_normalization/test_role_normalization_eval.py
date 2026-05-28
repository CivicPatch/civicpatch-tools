from enum import Enum
from pathlib import Path
from typing import Optional

import pytest
import yaml
from pydantic import BaseModel
from shared.utils.config_utils import RoleConfig
from utils import people_utils

CASES_PATH = Path(__file__).parent / "cases.yml"
TAXONOMY_PATH = Path(__file__).parent / "taxonomy.yml"

NEW = "NEW"
DROP = "DROP"


class Scope(BaseModel):
    state: Optional[str] = None
    output_type: Optional[str] = None
    locality: Optional[str] = None


class EvalCase(BaseModel):
    raw_string: str
    scope: Scope
    expected: str


class Disposition(str, Enum):
    correct = "correct"
    false_positive = "false_positive"
    false_negative = "false_negative"
    wrong_match = "wrong_match"


class Outcome(BaseModel):
    case: EvalCase
    actual: list[str]
    disposition: Disposition
    confidence: Optional[float] = None


class EvalReport(BaseModel):
    total: int
    correct: int
    false_positives: int
    false_negatives: int
    by_disposition: dict[Disposition, int]


def parse_cases(raw: list[dict]) -> list[EvalCase]:
    return [EvalCase.model_validate(row) for row in raw]


def validate_cases(cases: list[EvalCase], taxonomy: RoleConfig) -> None:
    allowed = {NEW, DROP, *(entry.role for entry in taxonomy.roles)}
    unknown = [c for c in cases if c.expected not in allowed]
    if unknown:
        details = "\n".join(
            f"  {c.raw_string!r} → expected={c.expected!r}" for c in unknown
        )
        raise ValueError(
            "cases.yml has expected values not in taxonomy or sentinels:\n" + details
        )


def score_case(case: EvalCase, actual: list[str]) -> Outcome:
    """Classify the matcher's output for one case into a Disposition."""
    actual_titled = [a.title() for a in actual]
    produced_no_role = len(actual) == 0 or actual_titled == [case.raw_string.title()]

    if case.expected in (NEW, DROP):
        disposition = Disposition.correct if produced_no_role else Disposition.false_positive
    elif case.expected.title() in actual_titled:
        disposition = Disposition.correct
    elif produced_no_role:
        disposition = Disposition.false_negative
    else:
        disposition = Disposition.wrong_match

    return Outcome(case=case, actual=actual, disposition=disposition)


def summarize(outcomes: list[Outcome]) -> EvalReport:
    by_disposition: dict[Disposition, int] = {d: 0 for d in Disposition}
    for outcome in outcomes:
        by_disposition[outcome.disposition] += 1
    return EvalReport(
        total=len(outcomes),
        correct=by_disposition[Disposition.correct],
        false_positives=by_disposition[Disposition.false_positive],
        false_negatives=by_disposition[Disposition.false_negative],
        by_disposition=by_disposition,
    )


def _load_yaml(path: Path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_cases(path: Path, taxonomy: RoleConfig) -> list[EvalCase]:
    cases = parse_cases(_load_yaml(path))
    validate_cases(cases, taxonomy)
    return cases


def load_taxonomy(path: Path) -> RoleConfig:
    return RoleConfig.model_validate(_load_yaml(path))


REPORT_PATH = Path(__file__).parent / "eval-report.yml"


def build_report_data(report: EvalReport, outcomes: list[Outcome]) -> dict:
    return {
        "summary": {
            "total": report.total,
            "correct": report.correct,
            "false_positives": report.false_positives,
            "false_negatives": report.false_negatives,
            "wrong_matches": report.by_disposition[Disposition.wrong_match],
            "pct_correct": round(report.correct / report.total * 100, 1) if report.total else 0,
        },
        "dispositions": [
            {
                "raw_string": o.case.raw_string,
                "expected": o.case.expected,
                "actual": o.actual,
                "disposition": o.disposition.value,
            }
            for o in outcomes
        ],
    }


@pytest.mark.evals_roles
def test_role_normalization_eval():
    taxonomy: RoleConfig = load_taxonomy(TAXONOMY_PATH)
    cases: list[EvalCase] = load_cases(CASES_PATH, taxonomy)
    outcomes: list[Outcome] = [
        score_case(
            case, actual=people_utils.normalize_roles([case.raw_string], role_config=taxonomy)
        )
        for case in cases
    ]
    report = summarize(outcomes)
    data = build_report_data(report, outcomes)
    REPORT_PATH.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")
    assert report.false_positives == 0, report.by_disposition
