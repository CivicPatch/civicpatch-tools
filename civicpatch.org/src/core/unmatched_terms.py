"""The triage list: words from open memberships' page labels that no role or designation matched.

Worked out from the verbatim labels rather than stored, so adding an alias takes the term off the
list at once. Each distinct label is parsed once; how often it is used comes from the database.
"""

from collections import Counter
from collections.abc import Callable, Sequence

from pydantic import BaseModel

EXAMPLE_JURISDICTIONS = 3


class LabelUsage(BaseModel, frozen=True):
    """One verbatim label, and the open memberships and jurisdictions that carry it."""

    label: str
    membership_ids: tuple[str, ...]
    jurisdiction_ocdids: tuple[str, ...]


class TriageTerm(BaseModel, frozen=True):
    text: str
    occurrences: int
    jurisdictions: int
    examples: list[str]
    example_label: str


class _Tally(BaseModel):
    spellings: Counter[str] = Counter()
    labels: Counter[str] = Counter()
    membership_ids: set[str] = set()
    jurisdiction_ocdids: set[str] = set()


def triage_terms(
    usages: Sequence[LabelUsage], unmatched_of: Callable[[str], tuple[str, ...]]
) -> list[TriageTerm]:
    """Every unmatched term, most widespread first. Spellings differing only in case are one term."""
    tallies: dict[str, _Tally] = {}
    for usage in usages:
        for term in unmatched_of(usage.label):
            tally = tallies.setdefault(term.lower(), _Tally())
            tally.spellings[term] += len(usage.membership_ids)
            tally.labels[usage.label] += len(usage.membership_ids)
            tally.membership_ids.update(usage.membership_ids)
            tally.jurisdiction_ocdids.update(usage.jurisdiction_ocdids)
    terms = [_term(tally) for tally in tallies.values()]
    return sorted(terms, key=lambda term: (-term.jurisdictions, -term.occurrences, term.text.lower()))


def _term(tally: _Tally) -> TriageTerm:
    return TriageTerm(
        text=_most_used(tally.spellings),
        occurrences=len(tally.membership_ids),
        jurisdictions=len(tally.jurisdiction_ocdids),
        examples=sorted(tally.jurisdiction_ocdids)[:EXAMPLE_JURISDICTIONS],
        example_label=_most_used(tally.labels),
    )


def _most_used(counts: Counter[str]) -> str:
    return min(counts, key=lambda value: (-counts[value], value))
