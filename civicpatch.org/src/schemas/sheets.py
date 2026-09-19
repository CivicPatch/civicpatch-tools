"""A spreadsheet cell as the app writes it: what it says, and how it is marked."""

from pydantic import BaseModel


class SheetCell(BaseModel):
    value: str
    # Sheets API `Color`: red, green, blue as 0–1 floats.
    background: dict[str, float] | None = None
    note: str | None = None
