from runners.governing_law_collector.schemas import FinderAnswer
from shared.utils.layered_config import GoverningLawConfig


async def find(governing_law: GoverningLawConfig, name: str) -> FinderAnswer:
    """The state's own list decides: listed is a charter at its link, not listed is general law.
    Vermont's Title 24 Appendix first (1.7)."""
    raise NotImplementedError(f"state_index finder not built yet ({governing_law.charter_index_url}, {name})")
