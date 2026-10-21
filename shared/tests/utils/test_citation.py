"""Clauses from plan 1's markdown of the Vermont charters (Newport ch. 7, Winooski ch. 19, Hyde
Park ch. 225, Montpelier ch. 5) and Michigan's MCL 62.1 (Armada)."""

from shared.schemas import QuoteScope, SelectionMethod
from shared.utils.citation import (
    method_named_in_quote,
    quote_in_text,
    role_named_in_quote,
    supporting_quote,
)

NEWPORT = (
    "- **§ 6. Elections of officers at annual meeting**\n"
    "At the annual meeting the said corporations shall elect from among the legal voters of said City a"
    " Mayor, City Clerk, four aldermen, a City Treasurer, one Constable, three listers, three auditors,"
    " and three grand jurors, who shall hold office until the next annual meeting."
)
HYDE_PARK = (
    "- **§ 71. Appointed officers**\n"
    "(a) Within 14 days following the annual Village meeting, the Board of Trustees shall meet and, by a"
    " majority vote, shall appoint other Village officers as allowed by law, including the following:"
    " (1) One Village Clerk. (2) One Village Treasurer. (3) One Delinquent Tax Collector. (4) One"
    " Constable. (b) A vacancy in any appointive office may be filled for the duration of the unexpired"
    " term by the trustees. (Added 1999, No. M-11 (Adj. Sess.), § 2, eff. May 9, 2000.)\n"
    "- **§ 55. President**\n"
    "A President shall be elected for a term of one year and shall perform all duties required by this charter."
)
WINOOSKI = (
    "(9) To be responsible for the financial affairs of the City. (10) To appoint and, when deemed"
    " necessary for the good of the service, suspend or remove the following, who shall hold office at"
    " the will of the City Council: (A) a City Treasurer; (B) a City Attorney or firm; (C) an Auditor or"
    " firm; and (D) a Health Officer and his or her deputies."
)
MONTPELIER = (
    "- **§ 509. Election of City officers**\n"
    "(a) At the annual meeting, Montpelier voters shall elect from among the City voters a Mayor for a"
    " term of two years, a City Clerk for a term of three years, a City Council member from each district"
    " for a term of two years, and other elective City officers. (b) Each elected City officer shall hold"
    " office until a successor has been duly elected and qualified."
)
ARMADA = (
    "in each village, the following officers shall be elected: a president, 6 trustees, 1 clerk, and 1"
    " treasurer. The president and trustees constitute the council."
)

ALDERMEN = ["Alderperson", "alderman", "aldermen"]
VILLAGE_PRESIDENT = ["Village President", "president of the village", "village board president"]


def test_a_quote_is_found_whatever_its_spacing():
    assert quote_in_text("four\n aldermen,  a City   Treasurer", NEWPORT)


def test_a_quote_not_in_the_text_is_not_found():
    assert not quote_in_text("five aldermen", NEWPORT)


def test_a_role_is_named_however_the_law_spaces_it():
    assert role_named_in_quote("All Selectboard members shall be elected at large.", ["select board member"])


def test_a_role_is_named_by_a_whole_word_only():
    assert not role_named_in_quote("the Board of Selectmen", ["Board of Selectmen Chair"])


def test_appointed_does_not_name_an_election():
    assert not method_named_in_quote("a place to be appointed by the City Council", SelectionMethod.ELECTED_BY_VOTERS)


def test_the_word_voters_alone_does_not_name_an_election():
    assert not method_named_in_quote("a meeting of the voters of the City", SelectionMethod.ELECTED_BY_VOTERS)


def test_appointing_from_among_the_board_names_a_choice_by_its_members():
    """Johnson village's 1965 bylaws: the trustees pick their chairman from among themselves."""
    quote = "The Trustees shall immediately after the annual meeting appoint from among the Board, a Chairman"

    assert method_named_in_quote(quote, SelectionMethod.ELECTED_BY_MEMBERS)


def test_a_bare_name_in_a_list_gets_its_whole_sentence():
    quote = supporting_quote(NEWPORT, "four aldermen", ALDERMEN, SelectionMethod.ELECTED_BY_VOTERS)

    assert quote is not None
    assert quote.text.startswith("At the annual meeting the said corporations shall elect")
    assert quote.scope == QuoteScope.SENTENCE


def test_a_list_item_gets_its_lead_in_from_the_same_sentence():
    quote = supporting_quote(HYDE_PARK, "One Village Clerk.", ["Village Clerk"], SelectionMethod.APPOINTED)

    assert quote is not None
    assert quote.text.startswith("(a) Within 14 days")
    assert quote.text.endswith("(1) One Village Clerk.")


def test_a_list_item_past_the_lead_in_sentence_gets_the_section_body():
    quote = supporting_quote(HYDE_PARK, "(2) One Village Treasurer.", ["Village Treasurer"], SelectionMethod.APPOINTED)

    assert quote is not None
    assert quote.text.startswith("(a) Within 14 days")
    assert "(Adj. Sess.)" in quote.text
    assert quote.scope == QuoteScope.SECTION_BODY


def test_a_body_without_the_method_gets_its_heading():
    text = "- **§ 6. Elections of officers at annual meeting**\nThe Mayor and four aldermen shall hold office for one year."

    quote = supporting_quote(text, "four aldermen", ALDERMEN, SelectionMethod.ELECTED_BY_VOTERS)

    assert quote is not None
    assert quote.text.startswith("- **§ 6. Elections of officers")
    assert quote.scope == QuoteScope.SECTION


def test_a_sentence_does_not_end_at_a_section_number_or_session_law():
    text = "Elected as provided in 24 V.S.A. § 871. Each trustee shall serve one year. (Added 1999, No. M-11 (Adj. Sess.), eff. May 9, 2000.) The trustees shall elect a clerk."

    quote = supporting_quote(text, "Elected as provided", ["Trustee"], SelectionMethod.ELECTED_BY_VOTERS)

    assert quote is not None
    assert quote.text == "Elected as provided in 24 V.S.A. § 871. Each trustee shall serve one year."


def test_an_appointment_named_in_an_enumeration_of_powers():
    quote = supporting_quote(WINOOSKI, "a City Attorney or firm", ["City Attorney"], SelectionMethod.APPOINTED)

    assert quote is not None
    assert quote.text.startswith("(10) To appoint")


def test_a_locator_beside_the_claim_gets_the_sentence_that_makes_it():
    quote = supporting_quote(MONTPELIER, "a Mayor for a term of two years", ["Council Member"], SelectionMethod.ELECTED_BY_VOTERS)

    assert quote is not None
    assert "a City Council member from each district" in quote.text


def test_a_statutes_bare_president_does_not_name_the_village_president():
    assert supporting_quote(ARMADA, "a president, 6 trustees", VILLAGE_PRESIDENT, SelectionMethod.ELECTED_BY_VOTERS) is None


def test_a_charters_bare_president_does_not_name_the_village_president():
    assert supporting_quote(HYDE_PARK, "A President shall be elected", VILLAGE_PRESIDENT, SelectionMethod.ELECTED_BY_VOTERS) is None


def test_a_locator_not_in_the_text_supports_nothing():
    assert supporting_quote(NEWPORT, "five aldermen", ALDERMEN, SelectionMethod.ELECTED_BY_VOTERS) is None


def test_a_section_past_the_widest_quote_supports_nothing():
    text = "One Village Clerk. " + "The trustees shall meet. " * 80 + "They shall appoint officers."

    assert supporting_quote(text, "One Village Clerk.", ["Village Clerk"], SelectionMethod.APPOINTED) is None


LUNENBURG = (
    "At the annual meeting of said corporation, there shall be elected, by ballot if called for, for the"
    " ensuing year and until their successors are chosen, a Moderator, a Clerk, a Treasurer, one trustee"
    " for a term of one year, one trustee for a term of two years, and one trustee for a term of three years.\n"
    "- **§ 2. Meetings**\nThe trustees shall meet monthly."
)


def test_a_quote_shortened_with_an_ellipsis_is_found_when_its_pieces_are_in_order():
    locator = "there shall be elected, by ballot if called for, ... one trustee for a term of one year"

    quote = supporting_quote(LUNENBURG, locator, ["Trustee"], SelectionMethod.ELECTED_BY_VOTERS)

    assert quote is not None
    assert quote.text.startswith("At the annual meeting of said corporation")


def test_an_ellipsis_in_brackets_counts_as_one():
    locator = "there shall be elected [...] one trustee for a term of one year"

    assert supporting_quote(LUNENBURG, locator, ["Trustee"], SelectionMethod.ELECTED_BY_VOTERS) is not None


def test_pieces_out_of_order_locate_nothing():
    locator = "one trustee for a term of one year ... there shall be elected"

    assert supporting_quote(LUNENBURG, locator, ["Trustee"], SelectionMethod.ELECTED_BY_VOTERS) is None


def test_pieces_from_two_sections_locate_nothing():
    locator = "there shall be elected ... The trustees shall meet monthly"

    assert supporting_quote(LUNENBURG, locator, ["Trustee"], SelectionMethod.ELECTED_BY_VOTERS) is None


def test_with_no_method_naming_the_role_is_enough():
    text = "The Village Clerk shall keep the records of the Board."

    quote = supporting_quote(text, "The Village Clerk shall keep", ["Village Clerk"], None)

    assert quote is not None
    assert quote.text == text


def test_with_no_method_the_role_must_still_be_named():
    text = "The records of the Board shall be kept."

    assert supporting_quote(text, "The records of the Board", ["Village Clerk"], None) is None

