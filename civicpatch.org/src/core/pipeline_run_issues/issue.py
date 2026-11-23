from typing import Any

from pydantic import BaseModel
from shared.utils.statuses import PipelineIssueType, PipelineRunErrorType


class Issue(BaseModel):
    issue_type: PipelineIssueType | PipelineRunErrorType
    data: dict[str, Any] = {}
