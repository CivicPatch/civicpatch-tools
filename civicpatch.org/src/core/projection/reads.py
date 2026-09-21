"""When we last looked at an organization.

A read is "this changeset fetched this organization's page", and it is what retires people:
`membership_state` asks whether the latest read listed them. Two things count as one, a
`source_pages` row naming the organization, and any live record naming it, which is the rule
we have had all along and covers every changeset filed before that table existed.

Derived here rather than materialised by the loader because a read has no independent
existence: it *is* the statement that some live fact names the organization. Synthesise it
before withdraws are applied and a rolled-back scrape leaves behind a read that nothing can
withdraw, retiring people on the strength of a scrape that no longer exists.
"""

from datetime import datetime

from pydantic import BaseModel

from core.projection.facts import Facts


class Read(BaseModel, frozen=True):
    changeset_id: str
    created_at: datetime


def reads_of(organization_id: str, facts: Facts) -> tuple[Read, ...]:
    """Every changeset that read this organization, oldest first, once each.

    A changeset with both a page row and records counts once, timed by the page row: the row
    is when we looked, the records are only what we found.
    """

    time_by_changeset: dict[str, datetime] = {}

    for page in facts.reads:
        if organization_id in page.organization_ids:
            time_by_changeset[page.changeset_id] = page.created_at
    for record in facts.records:
        if record.organization_id == organization_id and not time_by_changeset.get(
            record.changeset_id
        ):
            time_by_changeset[record.changeset_id] = record.created_at

    reads = [
        Read(changeset_id=changeset_id, created_at=created_at)
        for changeset_id, created_at in time_by_changeset.items()
    ]
    return tuple(sorted(reads, key=lambda read: (read.created_at, read.changeset_id)))
