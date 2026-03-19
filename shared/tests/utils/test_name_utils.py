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


def test_build_canonical_map_fuzzy():
    identities = {}
    all_people = [{"name": "Jeffery David Martinez"}, {"name": "Jeffery Martinez"}]
    canonical_map = name_utils.build_canonical_map(all_people, identities)
    # Both should map to the same canonical name
    assert canonical_map["Jeffery David Martinez"] == canonical_map["Jeffery Martinez"]