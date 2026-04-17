from pydantic import BaseModel
from typing import Generic, TypeVar, Optional
from pydantic import ConfigDict

TData = TypeVar("TData")
TState = TypeVar("TState")

class PipelineRunContext(BaseModel, Generic[TData, TState]):
    model_config = ConfigDict(frozen=True)
    data: TData
    current_state: TState
    request_id: str
    created_at: float = 0
    updated_at: float = 0
    progress: int = 0
    pipeline_error_type: Optional[str] = None
    pipeline_issues: list[dict] = []
