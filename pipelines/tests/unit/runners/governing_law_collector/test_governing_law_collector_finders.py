import pytest

from runners.governing_law_collector.finders import classification
from shared.schemas import FoundBy, GoverningLawKind
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

    assert (answer.found_by, answer.kind, answer.classification, answer.urls) == (
        FoundBy.CLASSIFICATION, GoverningLawKind.GENERAL_LAW, "town", ["https://vt.gov/17/2646"]
    )


def test_a_classification_without_statutes_finds_none():
    answer = classification.find(_VERMONT, "Orleans village")

    assert (answer.kind, answer.classification, answer.urls) == (GoverningLawKind.NONE_FOUND, "village", [])


def test_no_classification_or_no_block_finds_none():
    assert classification.find(_VERMONT, "Averys gore").kind == GoverningLawKind.NONE_FOUND
    assert classification.find(None, "Weybridge town").kind == GoverningLawKind.NONE_FOUND
