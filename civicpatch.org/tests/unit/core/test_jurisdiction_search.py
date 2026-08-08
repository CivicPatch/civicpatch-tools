"""Unit tests for build_search_text — the blob a jurisdiction is findable by.

Everything a user might type goes in one string so the query never has to be parsed for
a state qualifier: "seattle wa" and "seattle washington" both match because the row
carries the code AND the state name. Pure function, no mocks.
"""

import pytest
from core.jurisdiction_search import (
    build_fuzzy_tokens,
    build_parent_ocdids,
    build_search_text,
    build_tsquery,
)

_ENTRY = {
    "id": "ocd-jurisdiction/country:us/state:wa/place:seattle/government",
    "name": "Seattle city",
    "population": 741440,
}


@pytest.mark.unit
def test_includes_name_state_code_and_state_name():
    assert build_search_text(_ENTRY, "wa", "Washington") == "seattle city wa washington"


@pytest.mark.unit
def test_lowercases_everything():
    text = build_search_text({"name": "King County"}, "WA", "Washington")
    assert text == text.lower()


@pytest.mark.unit
def test_includes_display_name_when_present():
    entry = {"name": "Seattle city", "display_name": "Seattle"}
    assert build_search_text(entry, "wa", "Washington") == (
        "seattle city seattle wa washington"
    )


@pytest.mark.unit
def test_omits_state_name_when_unknown():
    # No level='state' row synced yet — degrades to name + code rather than emitting
    # a stray separator. "seattle wa" still matches; "seattle washington" does not.
    assert build_search_text(_ENTRY, "wa", None) == "seattle city wa"


@pytest.mark.unit
def test_keeps_the_census_type_suffix():
    # "albion township" is a legitimate disambiguating query in MI, where Albion city
    # and Albion township are different governments.
    entry = {"name": "Albion township"}
    assert "township" in build_search_text(entry, "mi", "Michigan")


@pytest.mark.unit
def test_missing_name_does_not_emit_blank_tokens():
    assert build_search_text({}, "wa", "Washington") == "wa washington"


@pytest.mark.unit
def test_blank_fields_are_skipped_not_joined():
    entry = {"name": "Seattle city", "display_name": "   "}
    assert build_search_text(entry, "wa", "Washington") == "seattle city wa washington"


# ── build_tsquery ────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_every_token_is_required_and_prefix_matched():
    assert build_tsquery("seattle wa") == "seattle:* & wa:*"


@pytest.mark.unit
def test_punctuation_is_a_separator_not_a_token():
    # "seattle, wa" and "seattle wa" are the same search.
    assert build_tsquery("seattle, wa") == build_tsquery("seattle wa")


@pytest.mark.unit
def test_word_order_does_not_change_the_query_semantics():
    # Token-AND, so "texas houston" finds the same rows as "houston texas".
    assert set(build_tsquery("texas houston").split(" & ")) == set(
        build_tsquery("houston texas").split(" & ")
    )


@pytest.mark.unit
def test_tsquery_operators_in_user_input_cannot_reach_the_query():
    # Tokens are rebuilt from [0-9a-z] runs rather than escaped, so no operator survives.
    built = build_tsquery("seattle & wa | !x <-> (y)")
    assert built == "seattle:* & wa:* & x:* & y:*"


@pytest.mark.unit
def test_a_query_of_only_punctuation_searches_nothing():
    assert build_tsquery("!!! &&&") == ""


@pytest.mark.unit
def test_single_character_is_below_the_minimum():
    # One letter matches most of the corpus; the result is meaningless until keystroke 2.
    assert build_tsquery("s") == ""


@pytest.mark.unit
def test_empty_query_searches_nothing():
    assert build_tsquery("   ") == ""


@pytest.mark.unit
def test_digits_are_kept():
    # Real names contain them, e.g. "Section 8" style districts.
    assert build_tsquery("district 9") == "district:* & 9:*"


# ── build_fuzzy_tokens ───────────────────────────────────────────────────────


@pytest.mark.unit
def test_fuzzy_tokens_are_matched_separately_not_as_one_string():
    # word_similarity matches a single continuous extent, so "seatle wa" as one unit
    # matches nothing — the tokens have to be ANDed instead.
    assert build_fuzzy_tokens("seatle wa") == ["seatle", "wa"]


@pytest.mark.unit
def test_fuzzy_tokens_share_the_tier_one_tokenizer():
    # Both tiers must agree on what a token is, or they disagree about what matched.
    query = "seattle, wa"
    assert build_fuzzy_tokens(query) == [
        term.removesuffix(":*") for term in build_tsquery(query).split(" & ")
    ]


@pytest.mark.unit
def test_fuzzy_tokens_below_the_minimum_are_empty():
    assert build_fuzzy_tokens("s") == []
    assert build_fuzzy_tokens("  ") == []


# ── build_parent_ocdids ──────────────────────────────────────────────────────

_WA_STATE = "ocd-jurisdiction/country:us/state:wa/government"
_KING = "ocd-jurisdiction/country:us/state:wa/county:king/government"


@pytest.mark.unit
def test_recorded_parents_keep_their_order_most_specific_first():
    entry = {"id": "x", "parent_ocdids": [_KING, _WA_STATE]}
    assert build_parent_ocdids(entry, "wa", "local") == [_KING, _WA_STATE]


@pytest.mark.unit
def test_the_state_is_appended_when_upstream_omits_it():
    # County rows carry no parent_ocdids at all; NC and TN carry none anywhere.
    assert build_parent_ocdids({"id": _KING}, "wa", "counties") == [_WA_STATE]


@pytest.mark.unit
def test_the_state_is_not_duplicated_when_already_recorded():
    entry = {"id": "x", "parent_ocdids": [_KING, _WA_STATE]}
    assert build_parent_ocdids(entry, "wa", "local").count(_WA_STATE) == 1


@pytest.mark.unit
def test_a_state_is_not_its_own_parent():
    assert build_parent_ocdids({"id": _WA_STATE}, "wa", "state") == []
