"""Disposition-based accuracy for the officials eval.

Wiring only — the taxonomy and the arithmetic live in `utils.dispositions`. This module
knows the record shape and which comparator each field needs: phone through
libphonenumber, roles and designations through the taxonomy, everything else exact.

Two fields exist here that the averaged dimensions cannot express:

`person` — a loop over `expected` never visits a person the model invented, so person-level
false positives were invisible. That is what let all three providers extract
`Abelardo Gonzalez` from an email address, against a fixture that deliberately excludes
him, without the eval reporting anything.

`district` vs `designations_other` — only designations with `has_geographic_area` become a
`division_ocdid`, and those are the ones we publish. Scoring them together with Place and
Position hides which half is failing; measured 2026-08-15, all of the loss was in the
non-geographic half.

Split into its own module because the eval file is already far past the file-size ceiling.
"""

import pathlib

import phonenumbers
import yaml
from shared.schemas import Role, RoleConfig
from shared.utils import name_utils
from utils.dispositions import Disposition, Tally, classify_membership, classify_value, tally
from utils.divisions import designations_without_division, filter_geographic_designations
from utils.taxonomy import Taxonomy, build_taxonomy, normalize_designations, normalize_roles

ROLE_ALIASES_PATH = pathlib.Path("tests/prompts/datasets/local/role_aliases.yml")
SCALAR_FIELDS = ("email", "phone", "url", "start_date", "end_date", "image")
SET_FIELDS = ("roles", "district", "designations_other")
PERSON_FIELD = "person"
ALL_FIELDS = (PERSON_FIELD,) + SET_FIELDS + SCALAR_FIELDS


def build_eval_taxonomy() -> Taxonomy:
    """Real taxonomy functions, fixture-supplied data, no database.

    `normalize_roles` moved to taxonomy.py and gained a taxonomy argument; the eval still
    called the old one-arg people_utils version, so every run died on AttributeError. That
    old call defaulted role_config to None, so roles were never alias-resolved — only 2 of
    15 cases feed `known_roles` to the prompt, leaving the model to guess the wording and
    then be marked wrong for guessing differently. The aliases live in a fixture so the
    yardstick holds still; see that file for why.

    Lives here rather than in the eval module so the fixture audit scores with exactly the
    same taxonomy it does — an audit using different normalization reports differences that
    the scorer would never have counted.
    """
    data = yaml.safe_load(ROLE_ALIASES_PATH.read_text(encoding="utf-8")) or {}
    roles = [
        Role(id=label.lower().replace(" ", "-"), label=label, aliases=list(aliases or []))
        for label, aliases in (data.get("roles") or {}).items()
    ]
    return build_taxonomy(RoleConfig(roles=roles))


def _same_phone(actual: str, expected: str) -> bool:
    try:
        return phonenumbers.parse(actual, "US") == phonenumbers.parse(expected, "US")
    except phonenumbers.NumberParseException:
        return actual == expected


def _district(designations, taxonomy) -> list[str]:
    return filter_geographic_designations(normalize_designations(designations or [], taxonomy))


def _other_designations(designations, taxonomy) -> list[str]:
    return designations_without_division(normalize_designations(designations or [], taxonomy))


def _by_normalized_name(people) -> dict[str, object]:
    return {name_utils.normalize_name(person.name or ""): person for person in people}


def case_dispositions(actual, expected, taxonomy) -> dict[str, list[Disposition]]:
    """Classify one case's people and their fields. Pure."""
    actual_by_name = _by_normalized_name(actual)
    expected_by_name = _by_normalized_name(expected)

    found: dict[str, list[Disposition]] = {field: [] for field in ALL_FIELDS}
    found[PERSON_FIELD] = classify_membership(actual_by_name, expected_by_name)

    # Field accuracy is only meaningful for a person both sides agree exists. A missed
    # person is already one false negative at the person level; charging it again on every
    # field would double-count the same failure.
    for key in set(actual_by_name) & set(expected_by_name):
        actual_person, expected_person = actual_by_name[key], expected_by_name[key]
        found["roles"] += classify_membership(
            normalize_roles(actual_person.roles or [], taxonomy),
            normalize_roles(expected_person.roles or [], taxonomy),
        )
        found["district"] += classify_membership(
            _district(actual_person.designations, taxonomy),
            _district(expected_person.designations, taxonomy),
        )
        found["designations_other"] += classify_membership(
            _other_designations(actual_person.designations, taxonomy),
            _other_designations(expected_person.designations, taxonomy),
        )
        for field in SCALAR_FIELDS:
            disposition = classify_value(
                str(getattr(actual_person, field, None) or ""),
                str(getattr(expected_person, field, None) or ""),
                equals=_same_phone if field == "phone" else None,
            )
            if disposition is not None:
                found[field].append(disposition)
    return found


def merge_dispositions(per_case) -> dict[str, list[Disposition]]:
    merged: dict[str, list[Disposition]] = {field: [] for field in ALL_FIELDS}
    for case in per_case:
        for field, dispositions in case.items():
            merged[field] += dispositions
    return merged


def summarize(merged) -> dict[str, Tally]:
    return {field: tally(dispositions) for field, dispositions in merged.items()}


def as_report(summary: dict[str, Tally]) -> dict[str, dict]:
    """Report shape: counts alongside rates, so a rate computed from four comparisons is
    visibly that rather than looking like a measurement."""
    return {
        field: {
            "correct": t.correct,
            "missing": t.false_negative,
            "spurious": t.false_positive,
            "wrong": t.wrong_match,
            "precision": t.precision,
            "recall": t.recall,
            "f1": t.f1,
        }
        for field, t in summary.items()
    }
