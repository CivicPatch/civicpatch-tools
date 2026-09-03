from pydantic import BaseModel


class SheetSyncRequestSchema(BaseModel):
    """Which state to re-sync. Absent means every state, through the nightly sweep's own path."""

    state: str | None = None
