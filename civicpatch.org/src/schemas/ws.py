from typing import Literal

from pydantic import BaseModel


class SubscribeMessage(BaseModel):
    action: Literal["subscribe", "unsubscribe"]
    topics: list[str]
