from typing import Any

from pydantic import BaseModel, Field

from shared.utils.statuses import ChangeLogType


class FieldChange(BaseModel):
    field: str
    from_: Any | None = Field(default=None, serialization_alias="from")
    to: Any | None = None


class PersonChangePayload(BaseModel):
    person_id: str
    person_name: str
    fields: list[FieldChange]


class PersonChange(BaseModel):
    type: ChangeLogType
    payload: PersonChangePayload
