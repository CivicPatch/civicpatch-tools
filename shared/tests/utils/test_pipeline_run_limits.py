"""The per-run spend ceiling, and where it comes from.

`pipeline.yml` is the package default; a state's `pipeline_run_cap_usd` overrides it for one run,
arriving through the dispatch. There is deliberately no env override — that one swallowed a
malformed value and carried on with the default, so a typo read as "no override was set".
"""

from decimal import Decimal

import pytest

from shared.utils.config_utils import load_pipeline_run_limits

pytestmark = pytest.mark.unit


def test_the_package_default_applies_when_no_state_set_a_cap():
    """Every local run and every unconfigured state lands here, so this is the common path."""
    assert load_pipeline_run_limits().pipeline_run_cap_usd == Decimal("0.20")


def test_a_states_cap_overrides_the_package_default():
    assert load_pipeline_run_limits(None, Decimal("0.05")).pipeline_run_cap_usd == Decimal("0.05")


def test_a_cap_of_zero_is_honoured_rather_than_read_as_unset():
    """`$0` means spend nothing on this state — a real setting, and exactly the one a falsy
    check would silently turn back into the $0.20 default."""
    assert load_pipeline_run_limits(None, Decimal("0")).pipeline_run_cap_usd == Decimal("0")


def test_the_override_does_not_disturb_the_rest_of_the_config():
    assert load_pipeline_run_limits(None, Decimal("0.05")).max_pages == load_pipeline_run_limits().max_pages
