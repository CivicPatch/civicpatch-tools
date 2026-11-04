"""The page check: the free filter asks nothing, and Jev's label and confidence decide the rest.
The Decisions endpoint is the faked boundary."""

import json
from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock
from runners.pipeline01_governing_law_collector.finders import page_check
from runners.pipeline01_governing_law_collector.schemas import LawKind, LawTarget
from services.open_router import decisions
from utils import cost_utils

pytestmark = pytest.mark.unit

_URL = "https://www.lanecountyor.gov/charter.pdf"
_OCDID = "ocd-jurisdiction/country:us/state:or/county:lane/government"
_TEXT = "# Home Rule Charter of Lane County\n\n## Section 1. Name\n\n" + "The county shall be governed by this charter. " * 40
_TARGET = LawTarget(kind=LawKind.CHARTER, description="municipal or county charter", terms=["Charter"], kept_labels=page_check.CHARTER_LABELS)


def _test(run: str = "run-1"):
    return page_check.page_test(_TARGET, "Lane County", run, _OCDID)


def _answer(httpx_mock: HTTPXMock, choice: str, confidence: float) -> None:
    httpx_mock.add_response(url=decisions.DECISIONS_URL, json={"answers": {decisions.QUESTION: {"choice": choice, "confidence": confidence}}, "usage": {"cost": 0.00006}})


@pytest.fixture(autouse=True)
def _token():
    with patch("services.open_router.decisions.get_env_vars", return_value={"OPEN_ROUTER_TOKEN": "test-token"}):
        yield


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "choice,confidence,kept",
    [
        ("charter", 0.99, True),
        ("charter", 0.6, True),
        ("amendment", 0.91, True),
        ("charter", 0.59, False),
        ("proposed", 0.99, False),
        ("other_place", 0.99, False),
        ("code", 1.0, False),
    ],
)
async def test_jevs_label_and_confidence_decide(httpx_mock: HTTPXMock, choice: str, confidence: float, kept: bool):
    _answer(httpx_mock, choice, confidence)

    assert await _test()(_TEXT, _URL) is kept


@pytest.mark.asyncio
@pytest.mark.parametrize("markdown", ["The charter, briefly.", "A long page about parks. " * 100], ids=["too short", "no word of law"])
async def test_what_the_filter_rejects_costs_no_question(httpx_mock: HTTPXMock, markdown: str):
    assert await _test()(markdown, _URL) is False
    assert httpx_mock.get_requests() == []


@pytest.mark.asyncio
async def test_the_question_sends_the_opening_and_headings_and_its_cost_is_recorded(httpx_mock: HTTPXMock):
    _answer(httpx_mock, "charter", 1.0)

    await _test("run-cost")(_TEXT + "the part past the opening " * 200, _URL)

    state = json.loads(httpx_mock.get_requests()[0].content)["state"]
    assert (state["place"], state["url"]) == ("Lane County", _URL)
    assert len(state["opening"]) == page_check.OPENING_CHARS
    assert state["headings"] == ["# Home Rule Charter of Lane County", "## Section 1. Name"]
    assert float(cost_utils.total_cost("run-cost")) == pytest.approx(0.00006)


@pytest.mark.asyncio
async def test_a_failing_endpoint_fails_the_check_rather_than_calling_the_page_not_law(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=decisions.DECISIONS_URL, status_code=500, is_reusable=True)

    with patch("utils.request_utils.asyncio.sleep"), pytest.raises(Exception, match="500"):
        await _test()(_TEXT, _URL)
