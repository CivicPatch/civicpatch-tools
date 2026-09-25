import re
from typing import Any, List

from pydantic import BaseModel, Field, field_validator, model_validator
from schemas.activity import RosterChange


class JurisdictionsByOcdidsRequest(BaseModel):
    ocdids: List[str]


# Sources give partial dates, so a term date is text: `SubmittedPersonRecord`'s three shapes.
_PARTIAL_DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


class OfficeEdit(BaseModel):
    """A post this person should hold, what to call their seat in it, and their term.

    `membership_label` is what this person's seat is called. A post's own name is
    `post_label`, a maintainer's act on the posts route, and is never edited here.
    `start_date` / `end_date` are the term, per membership: a person in two bodies has two.
    An omitted field is left alone; null clears it back to what the page says.
    """

    id: str
    membership_label: str | None = None
    start_date: str | None = None
    end_date: str | None = None

    @field_validator("start_date", "end_date")
    @classmethod
    def _a_partial_date(cls, value: str | None) -> str | None:
        if value is not None and not _PARTIAL_DATE.match(value):
            raise ValueError("a term date is YYYY, YYYY-MM or YYYY-MM-DD")
        return value


class PersonEdit(BaseModel):
    """One person as the client says they should be.

    `fields` holds only what changed; the server diffs it against the person the facts derive,
    so sending a value that already stands files nothing. `offices` is the whole set of posts
    they should hold, absent when the edit does not touch them and `[]` to remove the person
    from the roster. `same_as` merges this person into another and says nothing else.
    """

    id: str
    fields: dict[str, Any] | None = None
    offices: list[OfficeEdit] | None = None
    same_as: str | None = None

    @model_validator(mode="after")
    def _a_merge_stands_alone(self) -> "PersonEdit":
        if self.same_as is None:
            return self
        if self.same_as == self.id:
            raise ValueError("a person cannot be merged into themselves")
        # Claims filed against the merged id land on the survivor, so `offices: []` here would
        # remove the survivor.
        if self.fields is not None or self.offices is not None:
            raise ValueError("a merge carries no fields or offices")
        return self


class JurisdictionRosterEditRequest(BaseModel):
    # The jurisdiction is the path, not a field: one place says which roster this edits.
    people: list[PersonEdit]
    # The caller's own review, when the edit is part of one: the claims are filed under it
    # rather than as an unrelated jurisdiction edit.
    changeset_id: str | None = None


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


class TimelineIssue(BaseModel):
    """What a run reported about one changeset, whatever became of it since.

    `data` differs by type — `{}`, `{found, expected}`, `{error}` — so it is passed through
    rather than flattened to a key not every type has.
    """

    issue_type: str
    status: str
    data: dict = {}


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
    # Why it ended that way, and everything the run reported about it. `cost_cap_reached` is
    # the one that explains a short roster, and it was invisible here.
    dismissed_reason: str | None = None
    issues: list[TimelineIssue] = []
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
