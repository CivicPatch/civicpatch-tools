import pytest

from runners.pipeline03_people_collector.schemas import ProcessPageContentStep, ProgressState
from runners.pipeline03_people_collector.transitions.main import calculate_progress_percentage
from tests.factories.pipeline_run_context import pipeline_run_context_factory

pytestmark = pytest.mark.unit

LAST_STEP = 10


def _data(found: int, expected: int):
    data = pipeline_run_context_factory(steps={}).data
    step = ProcessPageContentStep(progress=ProgressState(current_data=found, required_data=expected))
    return data.model_copy(update={"process_page_content_step": step})


def test_finding_more_people_than_expected_does_not_pass_100_percent():
    assert calculate_progress_percentage(_data(found=8, expected=5), LAST_STEP) <= 100
