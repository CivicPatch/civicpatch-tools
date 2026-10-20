"""SELECT_SECTIONS' pure part over a trimmed copy of Burlington's charter (ch. 3) as plan 1's
converter writes it: the site's header, subchapter lines, a wrapped heading, reserved ranges."""

from pathlib import Path

import pytest

from runners.organizations_collector.sections import (
    GoverningLawPage,
    Section,
    fits_whole,
    heading_listing,
    joined,
    keyword_sections,
    picked,
    split_sections,
)

pytestmark = pytest.mark.unit

BURLINGTON = GoverningLawPage(
    source_url="https://legislature.vermont.gov/statutes/fullchapter/24APPENDIX/003",
    text=(Path(__file__).parent / "fixtures" / "vt_burlington_excerpt.md").read_text(),
)


def _headings(sections: list[Section]) -> list[str]:
    return [section.heading for section in sections]


def test_every_section_anchor_starts_a_section():
    assert _headings(split_sections([BURLINGTON])) == [
        "§ 2. Election boundaries",
        "§ 3. Election of Mayor and City Councilors",
        "§ 8. Person to  reside in ward or City district  if casting ballot for particular local",
        "§§ 32-35. \\[Reserved.\\]",
        "§ 124. Chair; clerk, records",
        "§§ 223, 224. \\[Reserved.\\]",
    ]


def test_a_page_from_a_publisher_with_no_known_format_splits_into_nothing():
    municode = GoverningLawPage(source_url="https://library.municode.com/tn/nashville/codes/code_of_ordinances", text=BURLINGTON.text)

    assert split_sections([municode]) == []


def test_the_sites_header_belongs_to_no_section():
    assert "The Vermont Statutes Online" not in joined(split_sections([BURLINGTON]))


def test_a_section_mark_in_a_history_note_does_not_split():
    election = split_sections([BURLINGTON])[1]

    assert "(Amended 1997, No. M-18, (Adj. Sess.), § 2, eff. April 23, 1998" in election.text


def test_a_wrapped_heading_keeps_its_next_line_in_the_section():
    wrapped = split_sections([BURLINGTON])[2]

    assert "officers" in wrapped.text


def test_each_section_knows_its_subchapter():
    groups = [section.group for section in split_sections([BURLINGTON])]

    assert groups[:2] == [
        "Subchapter 001: Incorporation; City and Ward Boundaries",
        "Subchapter 002: Elections and City Meetings; City Elections",
    ]


def test_ids_run_across_pages():
    ids = [section.id for section in split_sections([BURLINGTON, BURLINGTON])]

    assert ids[0] == "H0001"
    assert ids[6] == "H0007"


def test_the_listing_shows_ids_under_their_subchapters():
    listing = heading_listing(split_sections([BURLINGTON]))

    assert listing.splitlines()[:3] == [
        "Subchapter 001: Incorporation; City and Ward Boundaries",
        "  H0001: § 2. Election boundaries",
        "Subchapter 002: Elections and City Meetings; City Elections",
    ]


def test_a_pick_comes_back_in_document_order_without_made_up_ids():
    found = split_sections([BURLINGTON])

    assert _headings(picked(found, ["H0005", "H0002", "H9999"])) == [
        "§ 3. Election of Mayor and City Councilors",
        "§ 124. Chair; clerk, records",
    ]


def test_the_keyword_fallback_keeps_the_composition_clause():
    assert "§ 3. Election of Mayor and City Councilors" in _headings(keyword_sections(split_sections([BURLINGTON])))


def test_the_keyword_fallback_leaves_out_reserved_sections():
    assert "§§ 32-35. \\[Reserved.\\]" not in _headings(keyword_sections(split_sections([BURLINGTON])))


def test_most_charters_fit_whole():
    assert fits_whole("x" * 21_000)
    assert not fits_whole("x" * 374_000)
