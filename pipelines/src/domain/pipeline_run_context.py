from pydantic import BaseModel
from typing import Generic, TypeVar, Optional
from pydantic import ConfigDict
from shared.utils.run_reports import RunFailure

TData = TypeVar("TData")
TState = TypeVar("TState")

class PipelineRunContext(BaseModel, Generic[TData, TState]):
    model_config = ConfigDict(frozen=True)
    data: TData
    current_state: TState
    pipeline_run_id: str
    created_at: float = 0
    updated_at: float = 0
    progress: int = 0
    # Set by the engine when a step raised; cp.org files the run's pipeline_error from it.
    failure: Optional[RunFailure] = None
