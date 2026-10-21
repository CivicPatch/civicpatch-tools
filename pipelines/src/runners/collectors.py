"""The collectors by kind: what the server door and the CLI start, and what config each is told.
A new collector is one entry here; its doors follow."""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from pydantic import BaseModel
from runners.pipeline01_governing_law_collector import main as governing_law_collector
from runners.pipeline01_governing_law_collector.schemas import GoverningLawCollectorConfig
from runners.pipeline02_organizations_collector import main as organizations_collector
from runners.pipeline02_organizations_collector.schemas import OrganizationsCollectorConfig
from shared.utils.statuses import PipelineRunKind


@dataclass(frozen=True)
class Collector:
    start: Callable[[str, str, Any], Awaitable[Any]]
    config: type[BaseModel]


COLLECTORS: dict[PipelineRunKind, Collector] = {
    PipelineRunKind.GOVERNING_LAW_COLLECTOR: Collector(start=governing_law_collector.start, config=GoverningLawCollectorConfig),
    PipelineRunKind.ORGANIZATIONS_COLLECTOR: Collector(start=organizations_collector.start, config=OrganizationsCollectorConfig),
}
