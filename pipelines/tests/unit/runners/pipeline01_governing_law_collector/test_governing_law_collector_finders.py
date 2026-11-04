from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runners.pipeline01_governing_law_collector import finders
from runners.pipeline01_governing_law_collector.finders import classification
from runners.pipeline01_governing_law_collector.schemas import GoverningLawCollectorConfig, LawKind, LawUrl, SearchResult
from shared.schemas import FoundBy
from shared.utils.layered_config import GoverningLawConfig

pytestmark = pytest.mark.unit
FINDERS = "runners.pipeline01_governing_law_collector.finders"

_VERMONT = GoverningLawConfig.model_validate({
    "charter_terms": ["Charter"],
    "classifications": {
        "town": {"lsad": ["town", "city"], "governed_by": "charter_or_general_law", "general_law": ["https://vt.gov/17/2646"]},
        "village": {"lsad": ["village"], "governed_by": "charter_or_general_law", "general_law": []},
    },
})


def test_the_lsads_classification_gives_its_general_law():
    answer = classification.find(_VERMONT, "Weybridge town")

    assert (answer.found_by, answer.classification, answer.law_urls) == (
        FoundBy.CLASSIFICATION, "town", [LawUrl(url="https://vt.gov/17/2646", kind=LawKind.STATUTE)]
    )


def test_a_classification_without_statutes_gives_nothing_to_fetch():
    answer = classification.find(_VERMONT, "Orleans village")

    assert (answer.classification, answer.urls) == ("village", [])


def test_no_classification_or_no_block_gives_nothing_to_fetch():
    assert classification.find(_VERMONT, "Averys gore").urls == []
    assert classification.find(None, "Weybridge town").urls == []


_OREGON = GoverningLawConfig.model_validate({
    "charter_terms": ["Charter"],
    "classifications": {"county": {"lsad": ["county"], "governed_by": "charter_else_general_law", "general_law": ["https://or.gov/203"]}},
})


@pytest.mark.asyncio
async def test_a_state_without_a_charter_index_searches_for_the_charter_with_the_statutes_beside():
    config = GoverningLawCollectorConfig(name="Lane County", url="https://www.lanecountyor.gov", governing_law=_OREGON)
    charter = LawUrl(url="https://www.lanecountyor.gov/charter", kind=LawKind.CHARTER)
    searched = AsyncMock(return_value=SearchResult(law_urls=[charter]))

    with patch(f"{FINDERS}.search.find", new=searched):
        answer = await finders.find(config, "run-1", "ocd-jurisdiction/country:us/state:or/county:lane/government", MagicMock())

    assert (answer.found_by, answer.classification) == (FoundBy.SEARCH, "county")
    assert answer.law_urls == [charter, LawUrl(url="https://or.gov/203", kind=LawKind.STATUTE)]
    target, _page_test, name, site = searched.await_args.args[:4]
    assert (target, name, site) == (finders.charter_target(_OREGON), "Lane County", "https://www.lanecountyor.gov")


@pytest.mark.asyncio
async def test_a_state_with_no_law_block_finds_nothing_and_asks_no_model():
    config = GoverningLawCollectorConfig(name="Averys gore", governing_law=None)

    with patch(f"{FINDERS}.search.find", new=AsyncMock()) as searched:
        answer = await finders.find(config, "run-1", "ocd-jurisdiction/country:us/state:vt/place:averys_gore/government", MagicMock())

    searched.assert_not_awaited()
    assert (answer.found_by, answer.urls) == (FoundBy.CLASSIFICATION, [])

