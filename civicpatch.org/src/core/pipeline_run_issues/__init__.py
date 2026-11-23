"""The issue a collector run files, from the report it sends at its end: the shared models each
pipeline's context extends (`shared.utils.run_reports`), read once from the uploaded context. A
failure first, whatever the kind; else the kind's own reader, one module each."""

from typing import Any, Callable, Optional

from shared.utils.run_reports import RunOutcome
from shared.utils.statuses import PipelineRunKind
from . import governing_law, organizations, people
from .failures import failure_issue
from .issue import Issue


# Each kind's context data, read into its report and decided.
ISSUE_READERS: dict[PipelineRunKind, Callable[[dict[str, Any]], Optional[Issue]]] = {
    PipelineRunKind.GOVERNING_LAW_COLLECTOR: governing_law.read,
    PipelineRunKind.ORGANIZATIONS_COLLECTOR: organizations.read,
    PipelineRunKind.PEOPLE_COLLECTOR: people.read,
}


def run_issue(kind: PipelineRunKind, context: dict[str, Any]) -> Optional[Issue]:
    """The one issue a collector run files: its failure if it failed, else what its kind reads."""
    failed = failure_issue(RunOutcome.model_validate(context))
    if failed is not None:
        return failed
    return ISSUE_READERS[kind](context["data"])
