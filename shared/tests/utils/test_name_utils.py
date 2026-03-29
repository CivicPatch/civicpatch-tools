import pytest
from nameparser import HumanName
from shared.utils import name_utils


def test_parses_basic_name():
    n = HumanName("John Smith")
    assert n.first == "John"
    assert n.last == "Smith"

def test_parses_middle_name():
    n = HumanName("John R. Smith")
    assert n.first == "John"
    assert n.middle == "R."
    assert n.last == "Smith"

def test_parses_jr_suffix_with_comma():
    n = HumanName("Martin Cantu, Jr.")
    assert n.first == "Martin"
    assert n.last == "Cantu"
    assert n.suffix == "Jr."

def test_parses_jr_suffix_without_comma():
    n = HumanName("Martin Cantu Jr.")
    assert n.first == "Martin"
    assert n.last == "Cantu"
    assert n.suffix == "Jr."

def test_parses_sr_suffix():
    n = HumanName("Martin C. Cantu, Sr.")
    assert n.first == "Martin"
    assert n.middle == "C."
    assert n.last == "Cantu"
    assert n.suffix == "Sr."

def test_parses_title():
    n = HumanName("Dr. John Smith")
    assert n.title == "Dr."
    assert n.first == "John"
    assert n.last == "Smith"

def test_parses_nickname():
    n = HumanName('John "Johnny" Smith')
    assert n.nickname == "Johnny"

def test_parses_full_name_with_middle_and_suffix():
    n = HumanName("Jeffery David Martinez")
    assert n.first == "Jeffery"
    assert n.middle == "David"
    assert n.last == "Martinez"

def test_exact_match():
    assert name_utils.exact_match("John Doe", "john doe")
    assert not name_utils.exact_match("John Doe", "Jane Doe")

def test_fuzzy_match():
    assert name_utils.fuzzy_match("Martin Cantu, Jr.", "Martin Cantu Jr.")
    assert name_utils.fuzzy_match("Jeffery David Martinez", "Jeffery Martinez")
    assert not name_utils.fuzzy_match("Martin Cantu, Jr.", "Martin C. Cantu, Sr.")


def test_fuzzy_match_one_char_substitution_in_first_name():
    assert name_utils.fuzzy_match("Emmanual Guerrero", "Emmanuel Guerrero")


def test_fuzzy_match_one_char_substitution_in_last_name():
    assert name_utils.fuzzy_match("John Smyth", "John Smith")


def test_last_name_match_different_first_names():
    assert name_utils.last_name_match("Ralph Buell", "Buster Buell")


def test_last_name_match_does_not_match_different_last_names():
    assert not name_utils.last_name_match("Ralph Buell", "Ralph Smith")


def test_fuzzy_match_does_not_match_two_char_diff():
    assert not name_utils.fuzzy_match("Jn Smith", "John Smith")


def test_within_one_edit_substitution():
    assert name_utils._within_one_edit("emmanual", "emmanuel")


def test_within_one_edit_insertion():
    assert name_utils._within_one_edit("john", "johnn")


def test_within_one_edit_identical():
    assert name_utils._within_one_edit("john", "john")


def test_within_one_edit_two_diffs():
    assert not name_utils._within_one_edit("jon", "johnn")

def test_normalize_name():
    assert name_utils.normalize_name("José Álvarez, Jr.") == "jose alvarez"
    assert name_utils.normalize_name("Martin Cantu, Jr.") == "martin cantu"

def test_build_canonical_map_with_identities():
    identities = {
        "Martin Cantu, Jr.": ["Martin Cantu Jr."],
        "Martin C. Cantu, Sr.": ["Martin C. Cantu"],
    }
    all_people = [{"name": "Martin Cantu Jr."}, {"name": "Martin C. Cantu"}]
    canonical_map = name_utils.build_canonical_map(all_people, identities)
    assert canonical_map["Martin Cantu Jr."] == "Martin Cantu, Jr."
    assert canonical_map["Martin C. Cantu"] == "Martin C. Cantu, Sr."

def test_normalize_text_for_search_lowercases():
    assert name_utils.normalize_text_for_search("Hello World") == "hello world"

def test_normalize_text_for_search_strips_accents():
    assert name_utils.normalize_text_for_search("José Álvarez") == "jose alvarez"

def test_normalize_text_for_search_strips_straight_apostrophe():
    assert name_utils.normalize_text_for_search("D'Agostino") == "dagostino"

def test_normalize_text_for_search_strips_curly_apostrophe():
    # U+2019 RIGHT SINGLE QUOTATION MARK
    assert name_utils.normalize_text_for_search("D\u2019Agostino") == "dagostino"

def test_normalize_text_for_search_both_apostrophe_variants_equal():
    straight = name_utils.normalize_text_for_search("D'Agostino")
    curly = name_utils.normalize_text_for_search("D\u2019Agostino")
    assert straight == curly


def test_exact_match_ignores_accents():
    assert name_utils.exact_match("aleman", "aléman")
    assert name_utils.exact_match("José Alvarez", "Jose Alvarez")


def test_fuzzy_match_ignores_accents():
    assert name_utils.fuzzy_match("José Martinez", "Jose Martinez")
    assert name_utils.fuzzy_match("María García", "Maria Garcia")


def test_last_name_match_ignores_accents():
    assert name_utils.last_name_match("John Alemán", "John Aleman")


def test_reorder_name_if_inverted_basic():
    assert name_utils.reorder_name_if_inverted("Kincannon, Laurie") == "Laurie Kincannon"

def test_reorder_name_if_inverted_with_suffix():
    assert name_utils.reorder_name_if_inverted("Smith, John Jr.") == "John Smith Jr."

def test_reorder_name_if_inverted_with_middle_name():
    assert name_utils.reorder_name_if_inverted("Burke, Rory Thomas") == "Rory Thomas Burke"

def test_reorder_name_if_inverted_no_comma_unchanged():
    assert name_utils.reorder_name_if_inverted("Laurie Kincannon") == "Laurie Kincannon"

def test_reorder_name_if_inverted_single_name_unchanged():
    assert name_utils.reorder_name_if_inverted("Kincannon") == "Kincannon"


def test_build_canonical_map_fuzzy():
    identities = {}
    all_people = [{"name": "Jeffery David Martinez"}, {"name": "Jeffery Martinez"}]
    canonical_map = name_utils.build_canonical_map(all_people, identities)
    # Both should map to the same canonical name
    assert canonical_map["Jeffery David Martinez"] == canonical_map["Jeffery Martinez"]