from unittest.mock import AsyncMock, patch

import pytest

from runners.engine import PipelineRunError
from runners.pipeline02_organizations_collector import main
from runners.pipeline02_organizations_collector.schemas import OrganizationsCollectorConfig
from shared.schemas import LLMCall
from shared.utils.layered_config import ConfigFile, merged_config
from utils import cost_utils

pytestmark = pytest.mark.unit

_RUN_ID = "run-start-1"
_OCDID = "ocd-jurisdiction/country:us/state:vt/place:stowe/government"
_CONFIG = OrganizationsCollectorConfig(
    name="Stowe town",
    governing_law=None,
    jurisdiction_config=merged_config(ConfigFile(), ConfigFile(), None),
    government_form=None,
)
_CALL = LLMCall(prompt_name="governing_role", gateway="openrouter", model="deepseek/deepseek-v4-flash", input_tokens=10, output_tokens=5)


async def _spend_then_fail(context, *_):
    cost_utils.get_cost_tracker(_RUN_ID).append(_CALL)
    raise PipelineRunError(_OCDID, context)


@pytest.mark.asyncio
async def test_a_run_that_fails_still_records_what_it_spent_and_drops_its_tally():
    with patch.object(main, "get_env_vars", return_value={"SERVICE_API_KEY": "key"}), patch.object(
        main, "run_pipeline", side_effect=_spend_then_fail
    ), patch.object(main.civicpatch_api, "record_llm_calls", new_callable=AsyncMock) as record:
        with pytest.raises(PipelineRunError):
            await main.start(_RUN_ID, _OCDID, _CONFIG)

    assert record.await_args is not None
    assert record.await_args.args[2:] == (_RUN_ID, [_CALL])
    assert cost_utils.get_cost_tracker(_RUN_ID) == []
