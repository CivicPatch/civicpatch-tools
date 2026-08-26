"""Disposition-based accuracy for the officials eval.

Wiring only — the taxonomy and the arithmetic live in `utils.dispositions`. This module
knows the record shape and which comparator each field needs: phone through
libphonenumber, the label through `parse_label`, everything else exact.

Two fields exist here that the averaged dimensions cannot express:

`person` — a loop over `expected` never visits a person the model invented, so person-level
false positives were invisible. That is what let all three providers extract
`Abelardo Gonzalez` from an email address, against a fixture that deliberately excludes
him, without the eval reporting anything.

`district` vs `designations_other` — only designations with `is_division` become a
`division_ocdid`, and those are the ones we publish. Scoring them together with Place and
Position hides which half is failing; measured 2026-08-15, all of the loss was in the
non-geographic half.

The set fields are no longer read off the record. The model now returns one label per
person, verbatim, and this module decomposes it — so a difference in wording that decomposes
the same way ("Councilman Pos. 4" vs "Council Member Position 4") stops counting as an
error, and the eval measures the components the product actually stores.

Split into its own module because the eval file is already far past the file-size ceiling.
"""

import pathlib
from collections import defaultdict

import yaml
from shared.schemas import Role, RoleConfig
from shared.utils import email_utils, name_utils, phone_utils, url_utils
from utils.dispositions import Disposition, Tally, classify_membership, classify_value, tally
from shared.utils.label_parser import ParsedLabel, parse_label
from shared.utils.taxonomy import Taxonomy, build_taxonomy, role_sort_key

ROLE_ALIASES_PATH = pathlib.Path("tests/prompts/datasets/local/role_aliases.yml")
# F1 floors on the disposition scoring — "would a regression here be visible", not "is this
# provider good". Provider quality is what comparison.yml is for.
#
# DERIVED, not guessed (2026-08-15, from 9 runs of the identical prompt in history.yml):
#     floor = worst observed run across the two candidate providers
#             MINUS one more swing of the same size
# A floor set inside a metric's own run-to-run swing flaps red on sampling noise and teaches
# everyone to ignore the gate. That is exactly what the previous guessed numbers did: `image`
# sat at 0.70 against a measured swing of 0.299, and `person` at 0.94 against runs spanning
# 0.930-0.992.
#
#   metric              min    max   swing   floor
#   roles              0.976  0.992  0.016    0.96
#   district           1.000  1.000  0.000    0.95   never moved in 9 runs
#   person             0.930  0.992  0.062    0.87
#   url                0.872  1.000  0.128    0.74
#   designations_other 0.833  1.000  0.167    0.67
#   email/phone/image/start_date/end_date   swing 0.27-0.56 -> ungateable
#
# The five at 0.0 are REPORT ONLY. Their swing swamps any floor that would also catch a real
# regression, so gating them would only produce noise. They stay visible in the accuracy
# block and the dashboard. Revisit once the corpus is larger — the stable core is currently
# 4 of 15 cases, and a bigger base is what would shrink these swings.
GATE_THRESHOLDS = {
    # Tier 1 — what the posts/memberships model is built on.
    #
    # `primary_role` carries the gate that `roles` used to, because it is the role the
    # product publishes. Inherits the 0.96 floor derived for `roles`, which is conservative:
    # a priority-only comparison has strictly fewer ways to fail, so this should be re-derived
    # from its own measured spread once the treatment arm has run.
    "primary_role": 0.96,
    "district": 0.95,
    # Tier 2 — gated with room sized to each metric's measured swing.
    "person": 0.87,
    "url": 0.74,
    "designations_other": 0.67,
    # Report only — see above. `roles` joins them: every role in the label, so a dropped
    # secondary office shows here while `primary_role` stays green. Worth watching — it
    # caught two prompt regressions on 2026-08-16 — but not worth failing a run over, since
    # only the highest-priority role is published.
    "roles": 0.0,
    "email": 0.0,
    "phone": 0.0,
    "image": 0.0,
    "start_date": 0.0,
    "end_date": 0.0,
}

SCALAR_FIELDS = ("email", "phone", "url", "start_date", "end_date", "image")
SET_FIELDS = ("primary_role", "roles", "district", "designations_other")
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


# The app's own normalizers, so the eval cannot fail a value the pipeline would have
# accepted. `normalize_record` runs exactly these over every scraped record before it is
# merged, so a scorer comparing raw strings measures formatting the product already
# discards: "HTTP://WWW.X.ORG/" and "https://x.org" are one URL to everything downstream.
#
# Dates and images have no app-side normalizer, so they stay exact — see the note in
# score_case on why plain equality is fair for them.
_FIELD_NORMALIZERS = {
    "phone": lambda value: phone_utils.normalize_phone_number(value) or "",
    "email": lambda value: email_utils.normalize_email(value) or "",
    "url": url_utils.canonical_url,
}


def normalize_field(field: str, value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalizer = _FIELD_NORMALIZERS.get(field)
    return normalizer(text) if normalizer else text


def _roles(parsed: list[ParsedLabel]) -> list[str]:
    """Every role, not just each label's winner: one label per person means a second office
    lives inside the same string, and reading only `role` would hide it from both sides."""
    return [role for p in parsed for role in p.roles]


def _primary_role(parsed: list[ParsedLabel], taxonomy: Taxonomy) -> list[str]:
    """The role this person is published under, since migration 111 has the highest-priority
    one usurp the rest. A list of nought or one, so `classify_membership` handles it like the
    other set fields."""
    roles = _roles(parsed)
    if not roles:
        return []
    return [min(roles, key=lambda role: role_sort_key(role, taxonomy))]


def _districts(parsed: list[ParsedLabel]) -> list[str]:
    """`designation:value`, not an ocdid — the ocdid needs a jurisdiction, and the eval runs
    every provider under a different one so that the cost tracker can key on it."""
    return [f"{p.division.designation}:{p.division.value}" for p in parsed if p.division]


def _other_designations(parsed: list[ParsedLabel]) -> list[str]:
    return [d for p in parsed for d in p.other_designations]


def group_by_name(people) -> dict[str, list]:
    """One person, all their labels. A person holding two offices is two records now, so the
    old `{name: person}` comprehension silently kept the last and dropped a label."""
    grouped: dict[str, list] = defaultdict(list)
    for person in people:
        grouped[name_utils.normalize_name(person.name or "")].append(person)
    return dict(grouped)


def _first_value(records, field: str) -> str:
    """Contact details belong to the person, not the seat, so any record carrying one
    answers for all of them."""
    for record in records:
        value = getattr(record, field, None)
        if value:
            return str(value)
    return ""


def case_dispositions(actual, expected, taxonomy) -> dict[str, list[Disposition]]:
    """Classify one case's people and their fields. Pure."""
    actual_by_name = group_by_name(actual)
    expected_by_name = group_by_name(expected)

    found: dict[str, list[Disposition]] = {field: [] for field in ALL_FIELDS}
    found[PERSON_FIELD] = classify_membership(actual_by_name, expected_by_name)

    # Field accuracy is only meaningful for a person both sides agree exists. A missed
    # person is already one false negative at the person level; charging it again on every
    # field would double-count the same failure.
    for key in set(actual_by_name) & set(expected_by_name):
        actual_records, expected_records = actual_by_name[key], expected_by_name[key]
        actual_parsed = [parse_label(r.label or "", taxonomy) for r in actual_records]
        expected_parsed = [parse_label(r.label or "", taxonomy) for r in expected_records]
        found["primary_role"] += classify_membership(
            _primary_role(actual_parsed, taxonomy), _primary_role(expected_parsed, taxonomy)
        )
        found["roles"] += classify_membership(_roles(actual_parsed), _roles(expected_parsed))
        found["district"] += classify_membership(
            _districts(actual_parsed), _districts(expected_parsed)
        )
        found["designations_other"] += classify_membership(
            _other_designations(actual_parsed), _other_designations(expected_parsed)
        )
        for field in SCALAR_FIELDS:
            disposition = classify_value(
                normalize_field(field, _first_value(actual_records, field)),
                normalize_field(field, _first_value(expected_records, field)),
            )
            if disposition is not None:
                found[field].append(disposition)
    return found


def case_mismatches(actual, expected, taxonomy) -> list[dict]:
    """Per-person expected/actual for every dimension that did not match.

    The dispositions say *that* a value is wrong; the dashboard has to show *what*. Built
    from the same grouping and the same comparators, so a row here cannot disagree with the
    tally it sits under. The label goes on every row because it is what makes the rest
    diagnosable — a wrong `district` is almost always a label the model read differently.
    """
    rows: list[dict] = []
    actual_by_name, expected_by_name = group_by_name(actual), group_by_name(expected)
    for key in sorted(set(actual_by_name) | set(expected_by_name)):
        actual_records = actual_by_name.get(key, [])
        expected_records = expected_by_name.get(key, [])
        name = (expected_records or actual_records)[0].name
        labels = {
            "expected_label": " | ".join(r.label for r in expected_records),
            "actual_label": " | ".join(r.label for r in actual_records),
        }
        if not expected_records or not actual_records:
            rows.append({
                "person": name, "field": PERSON_FIELD, **labels,
                "expected": "present" if expected_records else "—",
                "actual": "present" if actual_records else "—",
            })
            continue
        actual_parsed = [parse_label(r.label or "", taxonomy) for r in actual_records]
        expected_parsed = [parse_label(r.label or "", taxonomy) for r in expected_records]
        for field, extract in (
            ("primary_role", lambda p: _primary_role(p, taxonomy)),
            ("roles", _roles),
            ("district", _districts),
            ("designations_other", _other_designations),
        ):
            got, want = sorted(set(extract(actual_parsed))), sorted(set(extract(expected_parsed)))
            if got != want:
                rows.append({"person": name, "field": field, **labels,
                             "expected": want, "actual": got})
        for field in SCALAR_FIELDS:
            got = normalize_field(field, _first_value(actual_records, field))
            want = normalize_field(field, _first_value(expected_records, field))
            if got != want:
                rows.append({"person": name, "field": field, **labels,
                             "expected": want or "—", "actual": got or "—"})
    return rows


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
