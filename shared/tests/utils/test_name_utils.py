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

def test_same_name():
    assert name_utils.same_name("John Doe", "john doe")
    assert not name_utils.same_name("John Doe", "Jane Doe")

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

def test_name_grouping_key():
    assert name_utils.name_grouping_key("José Álvarez, Jr.") == "jose alvarez"
    assert name_utils.name_grouping_key("Martin Cantu, Jr.") == "martin cantu"

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


def test_same_name_ignores_accents():
    assert name_utils.same_name("aleman", "aléman")
    assert name_utils.same_name("José Alvarez", "Jose Alvarez")


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


def test_fuzzy_match_middle_initial_with_and_without_period():
    assert name_utils.fuzzy_match("John G. Sutton Jr.", "John G Sutton Jr.")


def test_fuzzy_match_does_not_match_jr_vs_sr_standard():
    # "Jim Barnett, Jr." parses suffix correctly — guard against regression
    assert not name_utils.fuzzy_match("Jim Barnett, Jr.", "Jim Barnett, Sr.")


def test_fuzzy_match_does_not_match_jr_vs_sr_title_position():
    # "Jr. Barnett Jim" (str(HumanName("Barnett, Jr., Jim"))) puts Jr./Sr. in title field
    assert not name_utils.fuzzy_match("Jr. Barnett Jim", "Sr. Barnett Jim")

def test_same_name_ignores_quote_style():
    assert name_utils.same_name("Dan O'Brien", "Dan O’Brien")
    assert name_utils.same_name('Patricia "Pat" Nolen', "Patricia “Pat” Nolen")


def test_same_name_ignores_suffix_comma_and_initial_period():
    assert name_utils.same_name("Richard T. Hale Jr.", "Richard T. Hale, Jr.")
    assert name_utils.same_name("John W Spelich", "John W. Spelich")


def test_same_name_ignores_credentials():
    assert name_utils.same_name("Dr. Frank Figueroa", "Frank Figueroa")
    assert name_utils.same_name("Holli P. Thier J.D.", "Holli P. Thier")
    assert name_utils.same_name("David M. Sander Ph.D.", "David M. Sander, Ph.D.")


def test_same_name_keeps_a_leading_md():
    assert not name_utils.same_name("Md Rahman", "Rahman")


def test_parse_name_strips_spaced_credential():
    assert name_utils.parse_name("Mark E. Henderson Ed. D").last == "Henderson"


def test_parse_name_reads_curly_quoted_nickname():
    parsed = name_utils.parse_name("Kenneth “Kenny” Parlet II")
    assert parsed.nickname == "Kenny"
    assert parsed.middle == ""


def test_fuzzy_match_across_credential():
    assert name_utils.fuzzy_match("Mark E. Henderson Ed. D", "Mark E. Henderson")


def test_fuzzy_match_middle_initial_matches_full_middle():
    assert name_utils.fuzzy_match("Jonathan A. Sanabria", "Jonathan Alexander Sanabria")
    assert not name_utils.fuzzy_match("Jonathan B. Sanabria", "Jonathan Alexander Sanabria")


def test_same_name_keeps_non_ascii_letters():
    assert not name_utils.same_name("王伟", "李娜")
    assert not name_utils.same_name("Søren Holm", "Sren Holm")


def test_same_name_folds_sharp_s():
    assert name_utils.same_name("Anna Straße", "Anna Strasse")


def test_same_name_ignores_invisible_characters():
    assert name_utils.same_name("John​ Smith", "John Smith")
    assert name_utils.same_name("John Smith", "John Smith")


def test_same_name_ignores_okina():
    assert name_utils.same_name("Kaʻiulani Kalama", "Kaiulani Kalama")


def test_fuzzy_match_tolerates_a_middle_that_is_only_punctuation():
    assert name_utils.fuzzy_match("John . Smith", "John A. Smith")


def test_parse_name_drops_any_title():
    parsed = name_utils.parse_name("Chair Hilda L. Solis")
    assert (parsed.title, parsed.first, parsed.last) == ("", "Hilda", "Solis")
    assert name_utils.parse_name("Col. Paul Cook").title == ""


def test_parse_name_keeps_a_title_that_is_the_first_name():
    assert name_utils.parse_name("Hon Lien").first == "Hon"
    assert name_utils.parse_name("Princess Washington").first == "Princess"


def test_parse_name_keeps_initials_that_look_like_a_suffix():
    parsed = name_utils.parse_name("JR Gonzales")
    assert (parsed.first, parsed.suffix) == ("JR", "")


def test_parse_name_moves_a_generational_title_to_the_suffix():
    parsed = name_utils.parse_name("Jr. Barnett Jim")
    assert (parsed.title, parsed.suffix) == ("", "Jr.")


def test_parse_name_keeps_only_generational_suffixes():
    assert name_utils.parse_name("Richard T. Hale, Jr., Ph.D.").suffix == "Jr."
    assert name_utils.parse_name("James Black M.D.").suffix == ""
    assert name_utils.parse_name("Garry Barbadillo Esq.").suffix == ""


def test_parse_name_does_not_read_md_as_a_title():
    parsed = name_utils.parse_name("Md Rahman")
    assert (parsed.first, parsed.last) == ("Md", "Rahman")


def test_parse_name_reads_curly_single_quoted_nickname():
    assert name_utils.parse_name("Gene ‘Gino’ Garcia").nickname == "Gino"


def test_same_name_ignores_name_order():
    assert name_utils.same_name("Smith, John", "John Smith")


def test_same_name_keeps_a_title_that_is_the_first_name():
    assert not name_utils.same_name("Hon Lien", "Lien")


def test_parse_name_rejoins_any_known_split_credential():
    assert name_utils.parse_name("David M. Sander Ph. D").last == "Sander"
    assert name_utils.parse_name("David M. Sander Ph. D").suffix == ""


def test_parse_name_leaves_trailing_initials_alone():
    parsed = name_utils.parse_name("Mary A. M")
    assert (parsed.first, parsed.middle, parsed.last) == ("Mary", "A.", "M")


@pytest.mark.parametrize(
    "written, plain",
    [
        ("Chair Hilda L. Solis", "Hilda L. Solis"),
        ("Dr. Frank Figueroa", "Frank Figueroa"),
        ("Richard T. Hale, Jr., Ph.D.", "Richard T. Hale, Jr."),
        ("Mark E. Henderson Ed. D", "Mark E. Henderson"),
        ("Holli P. Thier J.D.", "Holli P. Thier"),
    ],
)
def test_strip_titles_and_credentials(written, plain):
    assert name_utils.strip_titles_and_credentials(written) == plain


@pytest.mark.parametrize(
    "name",
    [
        'Jose "Chuy" Valerio',
        "Kenneth “Kenny” Parlet II",
        "Hon Lien",
        "JR Gonzales",
        "Md Rahman",
        "Solis, Hilda L.",
        "Mary D. Luffy",
        "Ed D. Luffy",
    ],
)
def test_strip_titles_and_credentials_leaves_the_rest_as_written(name):
    assert name_utils.strip_titles_and_credentials(name) == name


@pytest.mark.parametrize(
    "name1, name2",
    [
        ("Alex Walker-Griffin", "Alexander Walker-Griffin"),
        ("Jess Rivas", "Jessica Rivas"),
        ("Gino Garcia", 'Gene "Gino" Garcia'),
        ("Buddy Mendes", "Ernest Buddy Mendes"),
        ("Lock Dawson", "Patricia Lock Dawson"),
        ("Sheila Crippen Thomas", "Sheila Crippen-Thomas"),
        ("Maribel Aguilera", "Maribel Aguilera-Hernandez"),
    ],
)
def test_fuzzy_match_short_forms_names_gone_by_and_compound_surnames(name1, name2):
    assert name_utils.fuzzy_match(name1, name2)
    assert name_utils.fuzzy_match(name2, name1)


@pytest.mark.parametrize(
    "name1, name2",
    [
        ("Al Smith", "Alan Smith"),
        ("Maribel Hernandez", "Maribel Aguilera-Hernandez"),
        ("Sheila Thomas-Crippen", "Sheila Crippen-Thomas"),
    ],
)
def test_fuzzy_match_stays_strict_where_the_rules_stop(name1, name2):
    assert not name_utils.fuzzy_match(name1, name2)
