"""What governs a jurisdiction, and where its texts are. The state's index first, where it has
one; else a search for the charter, with the classification's general law beside it; a state
with no law block at all finds nothing."""

from . import classification, search, state_index
from ..schemas import FinderAnswer, GoverningLawCollectorConfig
from utils.log_utils import PipelineRunLogger


async def find(config: GoverningLawCollectorConfig, pipeline_run_id: str, jurisdiction_ocdid: str, logger: PipelineRunLogger) -> FinderAnswer:
    governing_law = config.governing_law
    if governing_law is None:
        return classification.find(governing_law, config.name)
    if governing_law.charter_link_list is not None:
        return await state_index.find(governing_law, config.name)
    return await search.find(governing_law, config.name, config.url, pipeline_run_id, jurisdiction_ocdid, logger)
