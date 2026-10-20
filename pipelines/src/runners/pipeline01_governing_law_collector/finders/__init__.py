"""What governs a jurisdiction, and where its texts are. The state's index first, where it has
one; then the classification's general law."""

from runners.pipeline01_governing_law_collector.finders import classification, state_index
from runners.pipeline01_governing_law_collector.schemas import FinderAnswer, GoverningLawCollectorConfig


async def find(config: GoverningLawCollectorConfig) -> FinderAnswer:
    governing_law = config.governing_law
    if governing_law is not None and governing_law.charter_link_list is not None:
        return await state_index.find(governing_law, config.name)
    return classification.find(governing_law, config.name)
