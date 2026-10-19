from typing import Optional

from runners.governing_law_collector.schemas import FinderAnswer
from shared.schemas import Finder, GoverningLawKind
from shared.utils.layered_config import GoverningLawConfig, resolve_classification


def find(governing_law: Optional[GoverningLawConfig], name: str) -> FinderAnswer:
    """General law by the name's LSAD alone. None found where the state has no block, the LSAD
    allows no single classification, or that classification lists no general law."""
    classification_id = resolve_classification(governing_law, name, None) if governing_law else None
    urls = governing_law.classifications[classification_id].general_law if governing_law and classification_id else []
    return FinderAnswer(
        finder=Finder.CLASSIFICATION,
        kind=GoverningLawKind.GENERAL_LAW if urls else GoverningLawKind.NONE_FOUND,
        classification=classification_id,
        urls=urls,
    )
