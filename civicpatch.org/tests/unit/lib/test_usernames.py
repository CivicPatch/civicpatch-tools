"""Tests for the pure pick functions in lib/usernames.py.

These verify the format of generated names and that the words come from the
configured wordlists. The orchestration (collision-aware fallback chain) is
tested at the route level in tests/unit/routers/test_user.py.
"""
import re

import pytest

from lib.usernames import (
    _ADJECTIVES,
    _NOUNS,
    _PLACES,
    append_numeric_suffix,
    append_place,
    pick_two_words,
)

TOKEN_RE = re.compile(r"^[a-z]+$")


@pytest.mark.unit
def test_wordlists_loaded_nonempty():
    # Sanity check — if the YAML failed to load or a key was renamed, these
    # would be empty and every other test in this file would be vacuous.
    assert len(_ADJECTIVES) > 0
    assert len(_NOUNS) > 0
    assert len(_PLACES) > 0


@pytest.mark.unit
def test_wordlists_contain_only_lowercase_tokens():
    for word in _ADJECTIVES + _NOUNS + _PLACES:
        assert TOKEN_RE.fullmatch(word), f"non-token word in lists: {word!r}"


@pytest.mark.unit
def test_pick_two_words_format():
    name = pick_two_words()
    assert re.fullmatch(r"[a-z]+-[a-z]+", name)


@pytest.mark.unit
def test_pick_two_words_components_come_from_lists():
    adj, noun = pick_two_words().split("-")
    assert adj in _ADJECTIVES
    assert noun in _NOUNS


@pytest.mark.unit
def test_append_place_adds_one_token_from_places_list():
    extended = append_place("apple-witch")
    assert extended.startswith("apple-witch-")
    third = extended.removeprefix("apple-witch-")
    assert third in _PLACES


@pytest.mark.unit
def test_append_numeric_suffix_adds_four_digit_number():
    suffixed = append_numeric_suffix("apple-witch-grove")
    assert re.fullmatch(r"apple-witch-grove-\d{4}", suffixed)


@pytest.mark.unit
def test_places_disjoint_from_nouns():
    # If a place word collided with a noun, we'd be able to produce names
    # like "youthful-meadow-meadow" once collision pushes to tier 2.
    assert set(_PLACES).isdisjoint(set(_NOUNS))
