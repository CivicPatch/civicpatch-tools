"""Find fixture defects by cross-provider agreement, using models as annotators.

The rule: where every sample agrees with every other and they all disagree with the
fixture, suspect the fixture. Independent providers converging on the same wrong answer is
far less likely than one hand-written expectation being wrong — every defect corrected on
2026-08-15 was found this way (an "At-Large" hyphen, a term end inferred from a candidacy
filing deadline, a group photo assigned to five people as their portraits).

It reports candidates; it does not edit anything. Each one still has to be checked against
the case's input.md, because unanimity is evidence and not proof — all three providers also
agree on extracting `Abelardo Gonzalez` from an email address, where the fixture is right
and the models are wrong.

Run:  uv run python tests/prompts/tests/evals/audit_fixtures.py [extra_run_dir ...]
"""

import pathlib
import sys

import yaml
from accuracy import _same_phone, build_eval_taxonomy
from eval_utils import PROVIDER_COMPARISON
from shared.utils import name_utils
from utils.taxonomy import normalize_designations, normalize_roles

CASES = pathlib.Path("tests/prompts/datasets/local/municipal_officials")
FIELDS = ("phone", "email", "url", "image", "start_date", "end_date")

# Only the providers currently under comparison. Old runs leave `-actual.yml` behind for
# providers since dropped, and those were produced by a different prompt and model — folding
# them into a unanimity vote weights a stale answer the same as a current one.
CURRENT = [f"open_router-{p.split(':', 1)[1]}" for p in PROVIDER_COMPARISON]


def _matches(field: str, produced: str, fixture: str) -> bool:
    """The scorer's equality, not string equality. Compare raw and every `austin_council`
    phone looks like a defect — `(512) 978-2100` against `512-978-2100` — when the scorer
    parses both through libphonenumber and calls them equal."""
    if field == "phone" and produced and fixture:
        return _same_phone(produced, fixture)
    return produced == fixture


def _people(path: pathlib.Path) -> list[dict] | None:
    """None means the run produced no file; [] means it ran and correctly found nobody.

    Collapsing those two loses the hallucination cases entirely: when seven samples return
    nothing and two invent a person, dropping the empties leaves the two looking unanimous.
    """
    if not path.exists():
        return None
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("people") or []


def _samples(case: pathlib.Path, roots: list[pathlib.Path]) -> list[list[dict]]:
    found = []
    for root in roots:
        directory = case if root == CASES else root / case.name
        found += [_people(directory / f"{name}-actual.yml") for name in CURRENT]
    return [s for s in found if s is not None]


def _unanimous(values: list[str]) -> str | None:
    """The one value every sample produced, or None if they disagreed at all."""
    return values[0] if values and len(set(values)) == 1 else None


def audit(roots: list[pathlib.Path]) -> list[dict]:
    candidates = []
    for case in sorted(CASES.iterdir()):
        if not case.is_dir() or not (case / "expected.yml").exists():
            continue
        expected = _people(case / "expected.yml") or []
        samples = _samples(case, roots)
        if len(samples) < 2:
            continue
        source = (case / "input.md").read_text(encoding="utf-8", errors="ignore")
        by_name = [
            {name_utils.normalize_name(p.get("name", "")): p for p in sample}
            for sample in samples
        ]
        for person in expected:
            key = name_utils.normalize_name(person.get("name", ""))
            present = [s[key] for s in by_name if key in s]
            if len(present) < len(samples):
                continue
            for field in FIELDS:
                agreed = _unanimous([str(p.get(field) or "") for p in present])
                if agreed is None:
                    continue
                if _matches(field, agreed, str(person.get(field) or "")):
                    continue
                candidates.append(
                    {
                        "case": case.name,
                        "person": person.get("name"),
                        "field": field,
                        "fixture": person.get(field),
                        "all_samples_say": agreed or "(nothing)",
                        "samples": len(present),
                        # A value the models produced that is nowhere in the page is a
                        # shared hallucination, not a fixture defect. Never promote one.
                        "in_source": (agreed in source) if agreed else True,
                    }
                )
    return candidates


def audit_sets(roots: list[pathlib.Path]) -> list[dict]:
    """Same rule for roles and designations, normalized through the eval's own taxonomy so
    `At Large` and `At-Large` are not reported as a disagreement."""
    taxonomy = build_eval_taxonomy()
    candidates = []
    for case in sorted(CASES.iterdir()):
        if not case.is_dir() or not (case / "expected.yml").exists():
            continue
        expected = _people(case / "expected.yml") or []
        samples = _samples(case, roots)
        if len(samples) < 2:
            continue
        by_name = [
            {name_utils.normalize_name(p.get("name", "")): p for p in sample}
            for sample in samples
        ]
        for person in expected:
            key = name_utils.normalize_name(person.get("name", ""))
            present = [s[key] for s in by_name if key in s]
            if len(present) < len(samples):
                continue
            for field, normalize in (
                ("roles", normalize_roles),
                ("designations", normalize_designations),
            ):
                produced = [
                    tuple(sorted(normalize(p.get(field) or [], taxonomy))) for p in present
                ]
                agreed = _unanimous(produced)
                if agreed is None:
                    continue
                wanted = tuple(sorted(normalize(person.get(field) or [], taxonomy)))
                if agreed == wanted:
                    continue
                candidates.append(
                    {
                        "case": case.name,
                        "person": person.get("name"),
                        "field": field,
                        "fixture": list(wanted),
                        "all_samples_say": list(agreed),
                        "samples": len(present),
                        "in_source": True,
                    }
                )
    return candidates


def audit_extra_people(roots: list[pathlib.Path]) -> list[dict]:
    """People every sample produced that the fixture omits.

    Unanimity is weakest here: all three providers extract `Abelardo Gonzalez` from an email
    address in a case whose fixture deliberately excludes him, and the fixture is right. So
    these are prompts to go read the page, never a list to apply.
    """
    candidates = []
    for case in sorted(CASES.iterdir()):
        if not case.is_dir() or not (case / "expected.yml").exists():
            continue
        wanted = {
            name_utils.normalize_name(p.get("name", "")) for p in (_people(case / "expected.yml") or [])
        }
        samples = _samples(case, roots)
        if len(samples) < 2:
            continue
        produced = [
            {name_utils.normalize_name(p.get("name", "")): p.get("name") for p in sample}
            for sample in samples
        ]
        for name_key in set.intersection(*(set(s) for s in produced)):
            if name_key in wanted:
                continue
            candidates.append(
                {
                    "case": case.name,
                    "person": produced[0][name_key],
                    "field": "(person absent from fixture)",
                    "fixture": None,
                    "all_samples_say": "extracted by every sample",
                    "samples": len(samples),
                    "in_source": True,
                }
            )
    return candidates


def main() -> None:
    roots = [CASES] + [pathlib.Path(a) for a in sys.argv[1:]]
    candidates = audit(roots) + audit_sets(roots) + audit_extra_people(roots)
    if not candidates:
        print("No fixture candidates — every unanimous answer matches the fixture.")
        return
    print(f"{len(candidates)} candidate(s), from {len(roots)} run(s). Verify each against input.md.\n")
    for c in candidates:
        flag = "" if c["in_source"] else "   [NOT IN SOURCE — shared hallucination, do not promote]"
        print(f"  {c['case']}/{c['person']} — {c['field']} ({c['samples']} samples agree){flag}")
        print(f"      fixture:  {c['fixture']!r}")
        print(f"      all say:  {c['all_samples_say']!r}")


if __name__ == "__main__":
    main()
