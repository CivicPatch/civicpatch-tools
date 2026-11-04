"""When a run files `governing_law_not_found`: a search that stored no charter where one is
possible, or a run that stored nothing it was sent for. An index's silence is not an issue."""

import pytest
from runners.pipeline01_governing_law_collector.issues import governing_law_not_found
from runners.pipeline01_governing_law_collector.schemas import (
    FinderAnswer,
    GoverningLawCollectorConfig,
    GoverningLawCollectorData,
    Missing,
    TriedReason,
    TriedUrl,
)
from shared.schemas import FoundBy
from shared.utils.layered_config import GoverningLawConfig

pytestmark = pytest.mark.unit

_OCDID = "ocd-jurisdiction/country:us/state:or/county:lane/government"
_STATUTE = "https://www.oregonlegislature.gov/bills_laws/ors/ors203.html"
_TRIED = [TriedUrl(url="https://www.lanecountyor.gov", reason=TriedReason.SITE_CRAWLED)]


def _oregon(governed_by: str) -> GoverningLawCollectorConfig:
    governing_law = GoverningLawConfig.model_validate({
        "charter_terms": ["Charter"],
        "classifications": {"county": {"lsad": ["county"], "governed_by": governed_by, "general_law": [_STATUTE]}},
    })
    return GoverningLawCollectorConfig(name="Lane County", governing_law=governing_law)


def _data(
    answer: FinderAnswer, config: GoverningLawCollectorConfig, charter_pages: tuple[str, ...] = (), statute_pages: tuple[str, ...] = (), skipped: tuple[str, ...] = ()
) -> GoverningLawCollectorData:
    return GoverningLawCollectorData(
        jurisdiction_ocdid=_OCDID, config=config, answer=answer,
        charter_source_page_ids=list(charter_pages), general_law_source_page_ids=list(statute_pages), skipped_urls=list(skipped),
    )


def test_a_search_that_stored_the_statutes_but_no_charter_is_missing_the_charter():
    answer = FinderAnswer(found_by=FoundBy.SEARCH, classification="county", general_law_urls=[_STATUTE], tried=_TRIED)

    issue = governing_law_not_found(_data(answer, _oregon("charter_else_general_law"), statute_pages=("page-1",)))

    assert issue is not None
    assert (issue.missing, issue.tried, issue.skipped_urls) == (Missing.CHARTER, _TRIED, [])


def test_a_search_for_a_general_law_classification_expects_no_charter():
    answer = FinderAnswer(found_by=FoundBy.SEARCH, classification="county", general_law_urls=[_STATUTE], tried=_TRIED)

    assert governing_law_not_found(_data(answer, _oregon("general_law"), statute_pages=("page-1",))) is None


def test_a_run_that_stored_none_of_its_urls_is_missing_everything():
    answer = FinderAnswer(found_by=FoundBy.SEARCH, classification="county", general_law_urls=[_STATUTE], tried=_TRIED)

    issue = governing_law_not_found(_data(answer, _oregon("charter_else_general_law"), skipped=(_STATUTE,)))

    assert issue is not None
    assert (issue.missing, issue.skipped_urls) == (Missing.EVERYTHING, [_STATUTE])


def test_a_search_that_stored_the_charter_files_nothing():
    answer = FinderAnswer(found_by=FoundBy.SEARCH, classification="county", charter_urls=["https://www.lanecountyor.gov/charter"])

    assert governing_law_not_found(_data(answer, _oregon("charter_else_general_law"), charter_pages=("page-1",))) is None


def test_an_index_that_lists_no_charter_is_an_answer_not_an_issue():
    answer = FinderAnswer(found_by=FoundBy.STATE_INDEX, classification="county", general_law_urls=[_STATUTE])

    assert governing_law_not_found(_data(answer, _oregon("charter_or_general_law"), statute_pages=("page-1",))) is None


def test_a_place_with_nothing_to_look_for_files_nothing():
    answer = FinderAnswer(found_by=FoundBy.CLASSIFICATION, classification=None)

    assert governing_law_not_found(_data(answer, GoverningLawCollectorConfig(name="Stowe town", governing_law=None))) is None
