"""Request and response models for roster comparisons. The upload's field descriptions are what
an agent reads, in OpenAPI."""

from enum import StrEnum
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field, StringConstraints, model_validator

MAX_ROWS = 20_000
MAX_ROWS_PER_BATCH = 500
MAX_ROW_NUMBER = 2_147_483_647  # the column is a Postgres integer
MAX_VALUES_PER_FIELD = 20
MAX_EXTRA_COLUMNS = 50
MAX_CORRECTIONS = 1000


def _no_nul(value: str) -> str:
    # Postgres text and jsonb refuse NUL; refused here, it is a 422 instead of a 500 on insert.
    if "\x00" in value:
        raise ValueError("contains a NUL character")
    return value


def _lowercase(value: Any) -> Any:
    return value.lower() if isinstance(value, str) else value


ShortText = Annotated[str, StringConstraints(max_length=300), AfterValidator(_no_nul)]
LongText = Annotated[str, StringConstraints(max_length=2000), AfterValidator(_no_nul)]
Values = Annotated[list[ShortText], Field(max_length=MAX_VALUES_PER_FIELD)]
ExtraValue = LongText | int | float | bool | None


class PersonOutcome(StrEnum):
    MATCHED = "matched"
    POSSIBLE_MATCH = "possible_match"
    ONLY_IN_UPLOADED_DATA = "only_in_uploaded_data"
    ONLY_IN_CIVICPATCH = "only_in_civicpatch"


class FieldLevel(StrEnum):
    """`civicpatch_has_more`, `uploaded_data_has_more` and `overlap` (the ⚠ levels) still agree."""

    BOTH_EMPTY = "both_empty"
    UPLOADED_DATA_HAS_NONE = "uploaded_data_has_none"
    CIVICPATCH_HAS_NONE = "civicpatch_has_none"
    EQUAL = "equal"
    CIVICPATCH_HAS_MORE = "civicpatch_has_more"
    UPLOADED_DATA_HAS_MORE = "uploaded_data_has_more"
    OVERLAP = "overlap"
    DIFFERS = "differs"
    UNKNOWN = "unknown"


class ComparedField(StrEnum):
    ROLE = "role"
    EMAILS = "emails"
    PHONES = "phones"
    URLS = "urls"
    START_DATE = "start_date"


class CandidateReason(StrEnum):
    SAME_NAME = "same_name"
    NICKNAME = "nickname"


class UploadedRow(BaseModel):
    """One person from the uploaded data, already converted by the agent."""

    source_row: int = Field(
        ge=1, le=MAX_ROW_NUMBER, description="This person's row number in the original file."
    )
    jurisdiction_ocdid: ShortText = Field(
        min_length=1,
        description="The jurisdiction's ocdid. Look it up with find_jurisdiction; never guess.",
    )
    name: ShortText = Field(min_length=1, description="The person's name, first name first, no title.")
    role: ShortText | None = Field(default=None, description="The role as the uploaded data states it.")
    emails: Values = Field(default_factory=list)
    phones: Values = Field(default_factory=list)
    urls: Values = Field(default_factory=list)
    start_date: ShortText | None = Field(default=None, description="ISO date the term started.")
    not_compared: dict[ShortText, ExtraValue] = Field(
        default_factory=dict,
        max_length=MAX_EXTRA_COLUMNS,
        description="Any other column from the row, as a plain value, kept as uploaded and not compared.",
    )

    @model_validator(mode="before")
    @classmethod
    def _collect_not_compared(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        known = set(cls.model_fields)
        extra = {key: value for key, value in data.items() if key not in known}
        kept = {key: value for key, value in data.items() if key in known}
        return {**kept, "not_compared": {**kept.get("not_compared", {}), **extra}}


class RosterComparisonHeader(BaseModel):
    """What a batched upload starts with; its rows come in batches and its corrections at finish."""

    state: Annotated[str, BeforeValidator(_lowercase)] = Field(
        pattern=r"^[a-z]{2}$", description="Two-letter state code (lowercased)."
    )
    source_columns: dict[ShortText, Values] = Field(
        max_length=MAX_EXTRA_COLUMNS,
        description="Each field above (name, role, emails, …) → the original column(s) it came from.",
    )


Corrections = Annotated[
    list[LongText],
    Field(
        max_length=MAX_CORRECTIONS,
        description=(
            "Everything the conversion changed, citing row numbers: jurisdictions matched by search, "
            "names corrected, rows the user agreed to leave out. An empty list says nothing was changed."
        ),
    ),
]


class RosterComparisonUpload(RosterComparisonHeader):
    """A state's roster, converted from the user's file by the agent."""

    corrections: Corrections
    rows: list[UploadedRow] = Field(min_length=1, max_length=MAX_ROWS)


class DraftRows(BaseModel):
    rows: list[UploadedRow] = Field(
        min_length=1, max_length=MAX_ROWS_PER_BATCH, description=f"Up to {MAX_ROWS_PER_BATCH} rows."
    )


class DraftFinish(BaseModel):
    corrections: Corrections


class RosterComparisonDraft(BaseModel):
    """An upload being sent in batches."""

    id: str
    rows: int = Field(description="Rows received so far.")
    expires_at: str


class RowWarningCode(StrEnum):
    CANDIDATE_ALREADY_MATCHED = "candidate_already_matched"
    ROLE_NOT_RECOGNISED = "role_not_recognised"
    INVALID_EMAIL = "invalid_email"
    INVALID_PHONE = "invalid_phone"


class RowWarning(BaseModel):
    code: RowWarningCode
    message: str


class Candidate(BaseModel):
    person_id: str
    name: str
    reason: CandidateReason
    already_matched_by_row: int | None = Field(
        default=None, description="Set when another row is matched to this person: show a warning."
    )


class FieldComparison(BaseModel):
    level: FieldLevel
    uploaded: list[str]
    civicpatch: list[str]


class PersonComparison(BaseModel):
    """One uploaded row, one civicpatch person, or both."""

    outcome: PersonOutcome
    uploaded: UploadedRow | None = None
    person_id: str | None = None
    person_name: str | None = None
    candidates: list[Candidate] = Field(default_factory=list)
    fields: dict[ComparedField, FieldComparison] = Field(default_factory=dict)
    warnings: list[RowWarning] = Field(default_factory=list)
    post_roles: list[str] = Field(
        default_factory=list,
        description="civicpatch's post role of each open membership, by name; the role field's other civicpatch values are member roles.",
    )


class OutcomeCounts(BaseModel):
    matched: int = 0
    possible_match: int = 0
    only_in_uploaded_data: int = 0
    only_in_civicpatch: int = 0


class FieldCounts(BaseModel):
    """Over matched people: `outcomes.matched` is the denominator. Percentages are derived."""

    agreement: int = 0
    one_side_has_more: int = 0
    conflict: int = 0
    unknown: int = 0
    uploaded_data_has_it: int = 0
    civicpatch_has_it: int = 0


class ComparisonRates(BaseModel):
    outcomes: OutcomeCounts = Field(default_factory=OutcomeCounts)
    fields: dict[ComparedField, FieldCounts] = Field(default_factory=dict)
    rows_with_warnings: int = 0


class RejectedReason(StrEnum):
    UNKNOWN_JURISDICTION = "unknown_jurisdiction"
    OUTSIDE_STATE = "outside_state"


class RejectedRow(BaseModel):
    source_row: int
    jurisdiction_ocdid: str
    reason: RejectedReason


class RowsRefused(BaseModel):
    """A 422's detail when rows name no jurisdiction of the state: nothing was saved."""

    message: str
    rejected_count: int
    rejected: list[RejectedRow] = Field(description="The first of them; rejected_count says how many in all.")


class JurisdictionComparison(BaseModel):
    jurisdiction_ocdid: str
    rates: ComparisonRates
    people: list[PersonComparison]


class RunResult(BaseModel):
    state: str
    source_columns: dict[str, list[str]]
    corrections: list[str]
    rates: ComparisonRates
    jurisdictions_not_named: int


class RosterComparison(RunResult):
    """A whole run as the service computes it, before it is saved."""

    jurisdictions: list[JurisdictionComparison]


class RosterComparisonRun(RunResult):
    """A saved run's summary: everything but its people."""

    id: str
    started_by_user_id: str
    started_at: str


class JurisdictionRates(BaseModel):
    jurisdiction_ocdid: str
    rates: ComparisonRates


class RosterComparisonListRow(BaseModel):
    """One saved run, as the list of runs shows it."""

    id: str
    state: str
    started_at: str
    started_by: str = Field(description="The username of the maintainer who ran it.")
    jurisdictions_named: int
    rates: ComparisonRates


class RosterComparisonListItem(RosterComparisonListRow):
    page_url: str


class RosterComparisonCreated(BaseModel):
    id: str
    page_url: str = Field(description="The run's page on civicpatch, to give to the user.")
    rates: ComparisonRates


class RosterComparisonSummary(BaseModel):
    run: RosterComparisonRun
    page_url: str
    jurisdictions: list[JurisdictionRates] = Field(description="Most unmatched first.")


class FieldFilter(StrEnum):
    """Which people behind a field's counts: those it conflicts for, or those one side knows more for."""

    CONFLICT = "conflict"
    ONE_SIDE_HAS_MORE = "one_side_has_more"


class PeopleFilter(BaseModel):
    """Which of a run's people to list; with none, every one. `field` and `level` go together."""

    outcome: PersonOutcome | None = None
    field: ComparedField | None = None
    level: FieldFilter | None = None

    @model_validator(mode="after")
    def _field_and_level_together(self) -> "PeopleFilter":
        if (self.field is None) != (self.level is None):
            raise ValueError("field and level go together")
        return self


class RunPeopleQuery(PeopleFilter):
    """The query string of GET /roster-comparisons/{run_id}/people: one model, as FastAPI reads it."""

    page: int = Field(1, ge=1)
    per_page: int = Field(50, ge=1, le=200)


class RunPerson(BaseModel):
    """One person in a run's state-wide list, with the jurisdiction they were compared in."""

    jurisdiction_ocdid: str
    person: PersonComparison


class RunPeoplePage(BaseModel):
    """The house pagination shape (`schemas.pagination.paginated_response`), typed."""

    total_items: int
    page: int
    total_pages: int
    data: list[RunPerson]


class RosterComparisonListPage(BaseModel):
    """Saved runs, newest first, in the house pagination shape."""

    total_items: int
    page: int
    total_pages: int
    data: list[RosterComparisonListItem]


class DraftResponse(BaseModel):
    data: RosterComparisonDraft


class CreatedResponse(BaseModel):
    data: RosterComparisonCreated


class SummaryResponse(BaseModel):
    data: RosterComparisonSummary


class PeopleResponse(BaseModel):
    data: list[PersonComparison]
