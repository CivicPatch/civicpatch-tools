"""The message an agent reads when an upload's rows are refused."""

from schemas.roster_comparisons import RejectedRow

# Enough to see what went wrong; a large bad upload usually repeats one mistake.
MAX_REJECTED_LISTED = 50
MAX_ROW_NUMBERS_LISTED = 20


def refusal_message(state: str, rejected: list[RejectedRow]) -> str:
    lines = _refusal_lines(rejected)
    listed = "; ".join(lines[:MAX_REJECTED_LISTED])
    not_listed = len(lines) - MAX_REJECTED_LISTED
    more = f"; and {not_listed} more" if not_listed > 0 else ""
    return (
        f"Not saved (the whole upload, or this batch): rows with no single jurisdiction in {state}: "
        f"{len(rejected)}. Ask the user once per place, set the jurisdiction_ocdid they choose on those rows, "
        f"then send the whole upload, or this batch, again. {listed}{more}"
    )


def _refusal_lines(rejected: list[RejectedRow]) -> list[str]:
    """Rows refused for the same values, however capitalized, are one line for the user, not one per person."""
    rows_by_refusal: dict[str, list[RejectedRow]] = {}
    for row in rejected:
        rows_by_refusal.setdefault(_refusal_text(row).casefold(), []).append(row)
    return [
        f"rows {row_numbers([row.source_row for row in rows])}: {_refusal_text(rows[0])}"
        for rows in rows_by_refusal.values()
    ]


def _refusal_text(row: RejectedRow) -> str:
    return f"{_values_given(row)} ({_reason_and_candidates(row)})"


def _values_given(row: RejectedRow) -> str:
    values = []
    if row.jurisdiction_ocdid:
        values.append(row.jurisdiction_ocdid)
    if row.geoid:
        values.append(f"geoid {row.geoid}")
    if row.jurisdiction_name:
        values.append(repr(row.jurisdiction_name))
    return " + ".join(values)


def _reason_and_candidates(row: RejectedRow) -> str:
    if not row.candidates:
        return row.reason
    candidates = [f"{candidate.name} ({candidate.jurisdiction_ocdid})" for candidate in row.candidates]
    candidate_list = " or ".join(candidates)
    return f"{row.reason}: {candidate_list}"


def row_numbers(source_rows: list[int]) -> str:
    listed = ", ".join(str(row) for row in source_rows[:MAX_ROW_NUMBERS_LISTED])
    not_listed = len(source_rows) - MAX_ROW_NUMBERS_LISTED
    if not_listed > 0:
        return f"{listed} and {not_listed} more rows"
    return listed
