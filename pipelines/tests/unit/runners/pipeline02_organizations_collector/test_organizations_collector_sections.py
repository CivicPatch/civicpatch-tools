"""SELECT_SECTIONS' pure part over a trimmed copy of Burlington's charter (ch. 3) as plan 1's
converter writes it: the site's header, subchapter lines, a wrapped heading, reserved ranges."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from runners.pipeline02_organizations_collector.sections import (
    NO_HEADING,
    SECTION_MAX_CHARS,
    WHOLE_TEXT_CHARS,
    GoverningLawPage,
    Section,
    fits_whole,
    heading_listing,
    joined,
    keyword_sections,
    page_kind,
    pages_by_kind,
    picked,
    split_sections,
    unheaded_share,
)
from shared.schemas import FoundBy, GoverningLaw, GoverningLawKind
from shared.utils.layered_config import Classification, GovernedBy, GoverningLawConfig

pytestmark = pytest.mark.unit

BURLINGTON = GoverningLawPage(
    id="page-1",
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


LAKEVIEW = GoverningLawPage(
    id="page-3",
    source_url="https://www.townoflakeview.org/charter.pdf",
    text=(
        "THE CHARTER FOR THE TOWN OF LAKEVIEW\n"
        "WE THE PEOPLE of Lakeview, Oregon, confer upon our Town the following powers.\n"
        "Chapter I\n"
        "NAME AND BOUNDARIES\n"
        "Section 1. Title. This Charter may be referred to as the 2011 Town of Lakeview Charter.\n"
        "Section 2. Name. The Town continues as a municipal corporation, organized under\n"
        "chapter 345, General Laws of Oregon 1913.\n"
        "Chapter II\n"
        "COUNCIL\n"
        "Section 8. Council. The council consists of a mayor and four councilors.\n"
    ),
)


def test_a_page_with_no_known_format_splits_at_its_own_headings():
    assert _headings(split_sections([LAKEVIEW])) == [
        f"{NO_HEADING} THE CHARTER FOR THE TOWN OF LAKEVIEW",
        "Chapter I NAME AND BOUNDARIES",
        "Section 1. Title. This Charter may be referred to as the 2011 Town of Lakeview Charter.",
        "Section 2. Name. The Town continues as a municipal corporation, organized under",
        "Chapter II COUNCIL",
        "Section 8. Council. The council consists of a mayor and four councilors.",
    ]


def test_a_wrapped_reference_to_a_chapter_stays_in_its_section():
    name = split_sections([LAKEVIEW])[3]

    assert "chapter 345, General Laws of Oregon 1913." in name.text


def test_a_chapter_line_groups_the_sections_after_it():
    assert [section.group for section in split_sections([LAKEVIEW])][-1] == "Chapter II COUNCIL"


def test_a_page_with_no_known_format_loses_no_text():
    assert "".join(section.text for section in split_sections([LAKEVIEW])) == LAKEVIEW.text


def test_other_states_heading_styles_start_sections():
    page = LAKEVIEW.model_copy(update={"text": "Intro.\nSec. 2.04.010 Mayor elected.\nThe mayor is elected.\n## Article 3 Council\nThe council has seven members.\n"})

    assert _headings(split_sections([page])) == [f"{NO_HEADING} Intro.", "Sec. 2.04.010 Mayor elected.", "Article 3 Council"]


def test_a_page_whose_headings_go_unrecognised_reads_as_mostly_unheaded():
    page = LAKEVIEW.model_copy(update={"text": "MAYOR ELECTED\n" + "The mayor is elected by the voters. " * 400})

    assert unheaded_share(split_sections([page])) == 1.0
    assert unheaded_share(split_sections([LAKEVIEW])) < 0.5


def test_text_under_no_recognised_heading_is_listed_by_its_first_line():
    page = LAKEVIEW.model_copy(update={"text": "MAYOR ELECTED\nThe mayor is elected by the voters for two years.\n"})

    assert _headings(split_sections([page])) == [f"{NO_HEADING} MAYOR ELECTED"]


def test_each_unheaded_part_is_listed_by_its_own_first_line():
    page = LAKEVIEW.model_copy(update={"text": "MAYOR ELECTED\n" + "The mayor is elected. " * 200 + "\n\nCOUNCIL\n" + "The council has five members. " * 200})

    previews = _headings(split_sections([page]))

    assert previews[0] == f"{NO_HEADING} MAYOR ELECTED"
    assert f"{NO_HEADING} COUNCIL" in previews


def test_a_long_section_is_cut_into_parts_under_its_heading():
    long_page = LAKEVIEW.model_copy(update={"text": "Section 9. Powers.\n" + "The Town may act. " * 600})

    found = split_sections([long_page])

    assert len(found) > 1
    assert {section.heading for section in found} == {"Section 9. Powers."}
    assert all(len(section.text) <= SECTION_MAX_CHARS for section in found)
    assert "".join(section.text for section in found) == long_page.text


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


def test_charters_up_to_burlingtons_length_fit_whole():
    assert fits_whole("x" * 21_000)
    assert fits_whole("x" * 374_000)
    assert not fits_whole("x" * (WHOLE_TEXT_CHARS + 1))


_STATUTE_URL = "https://legislature.vermont.gov/statutes/section/24/033/00871"
_VERMONT = GoverningLawConfig(
    charter_terms=["charter"],
    classifications={"town": Classification(governed_by=GovernedBy.CHARTER_OR_GENERAL_LAW, general_law=[_STATUTE_URL])},
)


def _law(kind: GoverningLawKind, classification: str | None = "town") -> GoverningLaw:
    return GoverningLaw(
        kind=kind,
        classification=classification,
        found_by=FoundBy.STATE_INDEX,
        source_page_ids=["page-1"],
        collected_at=datetime(2026, 10, 19, tzinfo=timezone.utc),
        cost_usd=None,
    )


def test_a_charter_jurisdictions_page_at_its_classifications_general_law_url_is_general_law():
    statute = GoverningLawPage(id="page-3", source_url=_STATUTE_URL, text="")

    assert page_kind(statute, _law(GoverningLawKind.CHARTER), _VERMONT) == GoverningLawKind.GENERAL_LAW


def test_a_charter_jurisdictions_other_pages_are_its_charter():
    assert page_kind(BURLINGTON, _law(GoverningLawKind.CHARTER), _VERMONT) == GoverningLawKind.CHARTER


def test_with_no_classification_every_page_of_a_charter_jurisdiction_is_its_charter():
    statute = GoverningLawPage(id="page-3", source_url=_STATUTE_URL, text="")

    assert page_kind(statute, _law(GoverningLawKind.CHARTER, classification=None), _VERMONT) == GoverningLawKind.CHARTER


def test_a_general_law_jurisdictions_pages_are_general_law():
    assert page_kind(BURLINGTON, _law(GoverningLawKind.GENERAL_LAW), _VERMONT) == GoverningLawKind.GENERAL_LAW


_STATUTE = GoverningLawPage(id="page-3", source_url=_STATUTE_URL, text="")
_OREGON = GoverningLawConfig(
    charter_terms=["Charter"],
    classifications={"county": Classification(governed_by=GovernedBy.CHARTER_ELSE_GENERAL_LAW, general_law=[_STATUTE_URL])},
)


def test_where_a_charter_replaces_the_general_law_a_charter_jurisdiction_reads_its_charter_alone():
    law = _law(GoverningLawKind.CHARTER, classification="county")

    assert pages_by_kind([BURLINGTON, _STATUTE], law, _OREGON) == [(GoverningLawKind.CHARTER, [BURLINGTON])]


def test_where_a_charter_replaces_the_general_law_a_jurisdiction_without_one_reads_the_statutes():
    law = _law(GoverningLawKind.GENERAL_LAW, classification="county")

    assert pages_by_kind([_STATUTE], law, _OREGON) == [(GoverningLawKind.GENERAL_LAW, [_STATUTE])]


def test_where_the_general_law_fills_a_charters_silence_both_are_read():
    law = _law(GoverningLawKind.CHARTER)

    assert pages_by_kind([BURLINGTON, _STATUTE], law, _VERMONT) == [
        (GoverningLawKind.CHARTER, [BURLINGTON]),
        (GoverningLawKind.GENERAL_LAW, [_STATUTE]),
    ]
