from pydantic import BaseModel
from typing import Generic, TypeVar, Optional

TData = TypeVar("TData")
TState = TypeVar("TState")

class WorkflowContext(BaseModel, Generic[TData, TState]):
    data: TData
    current_state: TState
    request_id: Optional[str] = None

    class Config:
        allow_mutation = False  # makes it immutable (functional style)
