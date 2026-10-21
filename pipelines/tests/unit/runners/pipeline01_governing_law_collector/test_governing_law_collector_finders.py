import pytest
from runners.pipeline01_governing_law_collector.finders import classification
from shared.schemas import FoundBy
from shared.utils.layered_config import GoverningLawConfig

pytestmark = pytest.mark.unit

_VERMONT = GoverningLawConfig.model_validate({
    "charter_terms": ["Charter"],
    "classifications": {
        "town": {"lsad": ["town", "city"], "governed_by": "charter_or_general_law", "general_law": ["https://vt.gov/17/2646"]},
        "village": {"lsad": ["village"], "governed_by": "charter_or_general_law", "general_law": []},
    },
})


def test_the_lsads_classification_gives_its_general_law():
    answer = classification.find(_VERMONT, "Weybridge town")

    assert (answer.found_by, answer.classification, answer.charter_urls, answer.general_law_urls) == (
        FoundBy.CLASSIFICATION, "town", [], ["https://vt.gov/17/2646"]
    )


def test_a_classification_without_statutes_gives_nothing_to_fetch():
    answer = classification.find(_VERMONT, "Orleans village")

    assert (answer.classification, answer.urls) == ("village", [])


def test_no_classification_or_no_block_gives_nothing_to_fetch():
    assert classification.find(_VERMONT, "Averys gore").urls == []
    assert classification.find(None, "Weybridge town").urls == []

