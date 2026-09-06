from typing import List

from pydantic import BaseModel, Field
from schemas.change_logs import RosterChange


class JurisdictionsByOcdidsRequest(BaseModel):
    ocdids: List[str]


class JurisdictionSearchResult(BaseModel):
    jurisdiction_ocdid: str
    level: str
    # Display names of the row's parent_ocdids, most specific first — e.g.
    # ["King County", "Washington"]. The ocdid carries only slugs, and a slug's display
    # name lives on the parent's own row, so this cannot be derived client-side.
    # Empty where open-data records no parents (all of NC and TN, some of MI/NJ).
    parent_names: list[str] = []
    # Official name, Census type suffix intact ("Albion township"). The suffix
    # disambiguates — MI has an Albion city and an Albion township.
    name: str
    # Friendly form ("Albion"). Absent until open-data emits it; callers fall back.
    display_name: str | None = None
    population: int | None = None
    # The jurisdiction's official site. Already in the row's `data`, so this costs no query.
    url: str | None = None


class PaginationLinks(BaseModel):
    # "self" is unusable as an attribute name, so serialize under the alias. FastAPI
    # dumps response models by alias, matching the envelope /{state}/search returns.
    prev: str = ""
    next: str = ""
    self_link: str = Field("", alias="self")


class JurisdictionSearchResponse(BaseModel):
    total_items: int
    page: int
    total_pages: int
    limit: int
    data: list[JurisdictionSearchResult]
    links: PaginationLinks


class JurisdictionHistoryEntry(BaseModel):
    """One changeset on a jurisdiction's timeline: what it was, how it ended, what it changed.

    Replaces `PeoplePipelineRunHistory`, which this query claimed to return and never did: it
    named the run's status `status` and typed both timestamps as floats, while the rows carried
    `pipeline_run_status` and ISO strings.

    **What is deliberately absent: `is_running` and `awaiting_review`.** Whether a changeset is
    still in flight is `/jurisdictions/in-flight`'s question, and answering it here too meant two
    queries deriving the same fact from the same predicates — free to disagree, and costing this
    one an `AVAILABLE_FOR_REVIEW` EXISTS subquery per row. `review_status` went with them: it is
    the coarse three-way answer that `outcome` supersedes. So did `branch_name` and
    `jurisdiction_ocdid` — nothing read either, and the first cost a `make_job_branch` per row.

    `updated_at` is when the changeset's content last moved. It is **not** what a duration is
    measured against: a scrape's changeset is minted at ingest with `updated_at == created_at`,
    so measuring it read 0s for a run that took nine minutes. `pipeline_run_started_at`/`pipeline_run_finished_at`
    are the run's own clock, NULL for a changeset no run produced.
    """

    changeset_id: str
    created_at: str | None
    updated_at: str | None
    pipeline_run_started_at: str | None = None
    pipeline_run_finished_at: str | None = None
    # Why it ended that way, and what is still open on it. `cost_cap_reached` is the one
    # that explains a short roster, and it was invisible here.
    dismissed_reason: str | None = None
    issue_types: list[str] = []
    pipeline_run_status: str | None
    pipeline_run_progress: int | None
    change_url: str | None
    kind: str | None
    # When a *person* published it, not when the machine finished.
    published_at: str | None
    # The five-way answer: `published`, `pending`, a `DismissalReason`, or `unknown` when a
    # dismissal recorded no `dismiss_review` log. A plain str rather than an enum — it spans
    # three vocabularies, and restating them here would be a second source of truth.
    outcome: str
    # Display name, absent while pending. `CivicPatch` when a sweep decided rather than a person.
    resolved_by: str | None
    changes: list[RosterChange] = []
