"""`triage_terms`: label usage in, the triage list out."""

import pytest

from core.unmatched_terms import LabelUsage, triage_terms

_TERMS = {
    "Harbormaster": ("Harbormaster",),
    "Harbormaster, Ward 2": ("Harbormaster",),
    "harbormaster": ("harbormaster",),
    "Pound Keeper": ("Pound Keeper",),
    "Mayor": (),
}


def _usage(label: str, memberships: list[str], jurisdictions: list[str]) -> LabelUsage:
    return LabelUsage(
        label=label, membership_ids=tuple(memberships), jurisdiction_ocdids=tuple(jurisdictions)
    )


def _terms(*usages: LabelUsage):
    return triage_terms(usages, _TERMS.__getitem__)


@pytest.mark.unit
def test_a_membership_carrying_the_term_in_two_labels_counts_once():
    [term] = _terms(
        _usage("Harbormaster", ["m1"], ["a"]),
        _usage("Harbormaster, Ward 2", ["m1", "m2"], ["a"]),
    )

    assert term.occurrences == 2
    assert term.example_label == "Harbormaster, Ward 2"


@pytest.mark.unit
def test_spellings_differing_in_case_are_one_term_shown_as_the_most_used():
    [term] = _terms(
        _usage("Harbormaster", ["m1", "m2"], ["a"]),
        _usage("harbormaster", ["m3"], ["b"]),
    )

    assert term.text == "Harbormaster"
    assert term.jurisdictions == 2


@pytest.mark.unit
def test_breadth_outranks_frequency_and_a_matched_label_is_no_term():
    terms = _terms(
        _usage("Pound Keeper", ["m1", "m2", "m3"], ["a"]),
        _usage("Harbormaster", ["m4", "m5"], ["a", "b"]),
        _usage("Mayor", ["m6"], ["c"]),
    )

    assert [term.text for term in terms] == ["Harbormaster", "Pound Keeper"]
