from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from utils import cost_utils

pytestmark = pytest.mark.unit

_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
_RUN = "run-1"


@pytest.fixture(autouse=True)
def _clean_tracker():
    cost_utils.reset_cost_tracker(_RUN)
    yield
    cost_utils.reset_cost_tracker(_RUN)


def _add(cost_usd, error=None, gateway="openrouter", tokens=(10, 20), run=_RUN):
    cost_utils.record_call(
        MagicMock(),
        run,
        cost_utils.LLMCall(
            prompt_name="municipality_officials",
            gateway=gateway,
            model="deepseek/deepseek-v4-flash",
            upstream_provider="AtlasCloud",
            input_tokens=tokens[0],
            output_tokens=tokens[1],
            cost_usd=cost_usd,
            error=error,
        ),
    )


def test_the_total_is_what_the_providers_stated():
    _add(Decimal("0.01"))
    _add(Decimal("0.02"))
    assert cost_utils.total_cost(_RUN) == Decimal("0.03")


def test_a_call_with_no_stated_cost_is_absent_from_the_total():
    """Grounded Gemini calls state no cost. Counting them as zero would read as free."""
    _add(Decimal("0.01"))
    _add(None, gateway="google")
    assert cost_utils.total_cost(_RUN) == Decimal("0.01")


def test_a_billed_failure_still_counts_against_the_cap():
    """The point of recording before parsing: the call was paid for either way."""
    _add(Decimal("0.05"), error="ValidationError: bad json")
    assert cost_utils.total_cost(_RUN) == Decimal("0.05")


def test_the_error_is_on_the_record():
    _add(Decimal("0.05"), error="ValidationError: bad json")
    _add(Decimal("0.01"))
    reasons = [c["error"] for c in cost_utils.get_cost_tracker(_RUN)["llm_costs"]]
    assert reasons == ["ValidationError: bad json", None]


def test_no_calls_totals_zero_rather_than_raising():
    assert cost_utils.total_cost(_RUN) == Decimal("0.0")


def test_two_runs_for_one_jurisdiction_do_not_share_a_tally():
    """The bug this key exists to prevent: keyed on the ocdid, a retry inherited the first
    run's spend and the cap tripped on someone else's tokens."""
    _add(Decimal("0.01"))
    _add(Decimal("0.02"), run="run-2")
    try:
        assert cost_utils.total_cost(_RUN) == Decimal("0.01")
        assert cost_utils.total_cost("run-2") == Decimal("0.02")
    finally:
        cost_utils.reset_cost_tracker("run-2")


def test_every_llm_counts_toward_the_one_total():
    _add(Decimal("0.01"))
    _add(Decimal("0.02"), gateway="google")
    _add(Decimal("0.03"))
    assert cost_utils.total_cost(_RUN) == Decimal("0.06")


def test_tokens_are_kept_even_though_cost_is_no_longer_derived_from_them():
    _add(Decimal("0.01"), tokens=(111, 222))
    call = cost_utils.get_cost_tracker(_RUN)["llm_costs"][0]
    assert (call["input_tokens"], call["output_tokens"]) == (111, 222)
    assert "input_cost" not in call and "model_input_price_per_1m" not in call
