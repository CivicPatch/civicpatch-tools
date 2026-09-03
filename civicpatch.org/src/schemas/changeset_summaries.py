from datetime import date, datetime

from pydantic import BaseModel


class StateRollup(BaseModel):
    """One state's line on the cross-state summary: what is waiting, and how the last window went.

    `to_review` is a **stock** and is deliberately unwindowed — a changeset waiting 90 days is
    still waiting, and it is the one this page exists to surface. Everything else is a **flow**
    and is counted within the window.
    """

    state: str
    to_review: int
    # Longest wait in the queue, in days. 0 when the queue is empty, which reads correctly:
    # nothing has been waiting.
    oldest_days: int
    confirmed: int
    rejected: int
    errored: int
    # Roster edits, not changesets — an order of magnitude larger, so the label has to carry
    # the unit wherever this is rendered.
    roster_edits: int
    # Runs still going. Gates the scrape button — starting a second batch on top of a live one
    # is the mistake this exists to prevent.
    running: int
    last_run_at: datetime | None


class CalendarDay(BaseModel):
    """One state's activity on one day. Bucketed on `created_at` in UTC — see the query.

    A day with no runs has no row: the strip renders a fixed number of columns and fills the
    gaps itself, so sending zeroes would be one row per state per quiet day.
    """

    state: str
    day: date
    ok: int
    to_review: int
    failed: int
    # By kind as well as outcome. `sheet_import` is most of what runs, so a day reading "12 ok"
    # without saying no scraper produced them would mislead. Hand edits are not counted at all:
    # they have no run, so "ok" and "failed" say nothing about them.
    scrapes: int
    imports: int


class BucketRow(BaseModel):
    """One locality in a bucket, and why it is there when the bucket alone does not say.

    Structured rather than a rendered `note` string: phrasing "5 days waiting" server-side puts
    English in the payload and makes re-wording it a backend change. Exactly one of these is set
    per bucket — `days_waiting` for the queue, `failure_reason` for failures, neither for `ok`,
    where "it worked" needs no elaboration.
    """

    jurisdiction_ocdid: str
    # The page's URL, built by the same helper every other endpoint uses. Not derived in the
    # frontend: the folder encoding is reversible and belongs in one place.
    jurisdiction_path: str
    name: str | None
    days_waiting: int | None = None
    failure_reason: str | None = None


class BucketPage(BaseModel):
    """One page of a bucket, and how many it is a page of."""

    total: int
    rows: list[BucketRow]
