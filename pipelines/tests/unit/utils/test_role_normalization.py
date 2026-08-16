from pathlib import Path
from typing import Optional

import pytest
import yaml
from pydantic import BaseModel
from shared.schemas import RoleConfig, RoleStatus
from utils.dispositions import Disposition, Tally, tally
from shared.utils.taxonomy import build_taxonomy, normalize_roles

CASES_PATH = Path(__file__).parent / "role_normalization" / "cases.yml"
TAXONOMY_PATH = Path(__file__).parent / "role_normalization" / "taxonomy.yml"

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


class Outcome(BaseModel):
    case: EvalCase
    actual: list[str]
    disposition: Disposition
    confidence: Optional[float] = None


def parse_cases(raw: list[dict]) -> list[EvalCase]:
    return [EvalCase.model_validate(row) for row in raw]


def validate_cases(cases: list[EvalCase], taxonomy: RoleConfig) -> None:
    """Every case label must be consistent with the fixture taxonomy.

    - a canonical label must name a real (active) role in the taxonomy
    - DROP must correspond to an actual exclusion (status: excluded) entry
    - NEW must match no canonical, alias, or exclusion — so passthrough is the
      truthful expectation, not a missing-from-fixture accident

    Membership is EXACT (canonical/alias/exclusion strings), NOT the fuzzy matcher:
    a NEW string is allowed to fuzzy/suffix-match a canonical — catching that
    mis-map is the eval's job, not the validator's.
    """
    canonicals = set()      # active canonical role names (for the expected-label check)
    known = set()           # lowercased canonical + alias strings of active roles
    exclusions = set()      # lowercased role + alias strings of exclusion entries
    # Migration 109 flattened the taxonomy: `kind: canonical|exclusion` became a
    # four-value `status`, and `role` split into `id` (slug) + `label` (display).
    for entry in taxonomy.roles:
        if entry.status == RoleStatus.EXCLUDED:
            exclusions.add(entry.label.lower())
            for alias in entry.aliases:
                exclusions.add(alias.lower())
        else:
            canonicals.add(entry.label)
            known.add(entry.label.lower())
            for alias in entry.aliases:
                known.add(alias.lower())

    errors: list[str] = []
    for c in cases:
        raw = c.raw_string.lower()
        if c.expected == NEW:
            if raw in known or raw in exclusions:
                errors.append(f"{c.raw_string!r} labeled NEW but matches the taxonomy")
        elif c.expected == DROP:
            if raw not in exclusions:
                errors.append(f"{c.raw_string!r} labeled DROP but no taxonomy exclusion covers it")
        elif c.expected not in canonicals:
            errors.append(f"{c.raw_string!r} → expected={c.expected!r} is not a taxonomy canonical")

    if errors:
        raise ValueError(
            "cases.yml inconsistent with taxonomy:\n" + "\n".join(f"  {e}" for e in errors)
        )


def score_case(case: EvalCase, actual: list[str]) -> Outcome:
    """Classify the matcher's output for one case into a Disposition.

    "Emitted nothing" and "passed the raw string through" are distinct outcomes
    that mean opposite things by `expected`: a DROP must emit nothing (a passthrough
    is a leak → false_positive), while a NEW must pass through (emitting nothing
    loses the role → false_negative). They must not be conflated into one boolean.
    """
    actual_titled = [a.title() for a in actual]
    emitted_nothing = len(actual) == 0
    passed_through_raw = actual_titled == [case.raw_string.title()]

    if case.expected == DROP:
        disposition = Disposition.correct if emitted_nothing else Disposition.false_positive
    elif case.expected == NEW:
        if passed_through_raw:
            disposition = Disposition.correct
        elif emitted_nothing:
            disposition = Disposition.false_negative
        else:
            disposition = Disposition.false_positive
    elif case.expected.title() in actual_titled:
        disposition = Disposition.correct
    elif emitted_nothing or passed_through_raw:
        disposition = Disposition.false_negative
    else:
        disposition = Disposition.wrong_match

    return Outcome(case=case, actual=actual, disposition=disposition)


def summarize(outcomes: list[Outcome]) -> Tally:
    """Counting moved to `utils.dispositions.tally` — this file used to carry its own copy
    of the enum and the counter. Sharing them is what lets one dashboard read every eval,
    and it brings precision/recall/f1 along for free."""
    return tally(outcome.disposition for outcome in outcomes)


def _load_yaml(path: Path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_cases(path: Path, taxonomy: RoleConfig) -> list[EvalCase]:
    cases = parse_cases(_load_yaml(path))
    validate_cases(cases, taxonomy)
    return cases


def load_taxonomy(path: Path) -> RoleConfig:
    return RoleConfig.model_validate(_load_yaml(path))


pytestmark = pytest.mark.unit


def test_role_normalization():
    taxonomy: RoleConfig = load_taxonomy(TAXONOMY_PATH)
    cases: list[EvalCase] = load_cases(CASES_PATH, taxonomy)
    # normalize_roles moved to taxonomy.py and now takes a built Taxonomy rather than a
    # RoleConfig keyword. Same breakage the officials eval had; neither was caught because
    # evals are not part of `mise run tpipes`.
    matcher = build_taxonomy(taxonomy)
    outcomes: list[Outcome] = [
        score_case(case, actual=normalize_roles([case.raw_string], matcher))
        for case in cases
    ]
    report = summarize(outcomes)
    misses = [
        f"{o.case.raw_string!r} expected={o.case.expected!r} got={o.actual!r} ({o.disposition.value})"
        for o in outcomes
        if o.disposition is not Disposition.correct
    ]
    assert not misses, f"{report.correct}/{len(outcomes)} correct:\n  " + "\n  ".join(misses)
