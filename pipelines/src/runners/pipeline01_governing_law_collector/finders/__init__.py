"""What governs a jurisdiction, and where its texts are. The state's index first, where it has
one; else a search for the charter, with the classification's general law beside it; a state
with no law block at all finds nothing."""

from . import classification, page_check, search, state_index
from ..schemas import FinderAnswer, GoverningLawCollectorConfig, LawKind, LawTarget, as_law_urls
from shared.schemas import FoundBy
from shared.utils.layered_config import GoverningLawConfig, resolve_classification
from utils.log_utils import PipelineRunLogger

CHARTER_DESCRIPTION = "municipal or county charter"
CHARTER_SKIP_WORDS = ["school"]


def charter_target(governing_law: GoverningLawConfig) -> LawTarget:
    return LawTarget(
        kind=LawKind.CHARTER,
        description=CHARTER_DESCRIPTION,
        terms=governing_law.charter_terms,
        skip_words=CHARTER_SKIP_WORDS,
        kept_labels=page_check.CHARTER_LABELS,
    )


async def find(config: GoverningLawCollectorConfig, pipeline_run_id: str, jurisdiction_ocdid: str, logger: PipelineRunLogger) -> FinderAnswer:
    governing_law = config.governing_law
    if governing_law is None:
        return classification.find(governing_law, config.name)
    if governing_law.charter_link_list is not None:
        return await state_index.find(governing_law, config.name)
    return await _by_search(governing_law, config, pipeline_run_id, jurisdiction_ocdid, logger)


async def _by_search(
    governing_law: GoverningLawConfig, config: GoverningLawCollectorConfig, pipeline_run_id: str, jurisdiction_ocdid: str, logger: PipelineRunLogger
) -> FinderAnswer:
    classification_id = resolve_classification(governing_law, config.name, None)
    general_law = governing_law.classifications[classification_id].general_law if classification_id else []
    target = charter_target(governing_law)
    is_target = page_check.page_test(target, config.name, pipeline_run_id, jurisdiction_ocdid)
    found = await search.find(target, is_target, config.name, config.url, pipeline_run_id, jurisdiction_ocdid, logger)
    return FinderAnswer(
        found_by=FoundBy.SEARCH,
        classification=classification_id,
        law_urls=[*found.law_urls, *as_law_urls(general_law, LawKind.STATUTE)],
        tried=found.tried,
    )
