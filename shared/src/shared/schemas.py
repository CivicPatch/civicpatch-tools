import re
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum, StrEnum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from shared.utils.email_utils import is_valid_email
from shared.utils.phone_utils import normalize_phone_number
from shared.utils.url_utils import is_web_url


class PersonBase(BaseModel):
    """`people` columns, minus `source_urls` and `updated_at` — the subclasses disagree on
    whether those are required, and pyright rejects narrowing them in a subclass."""

    id: str = ""
    name: str
    other_names: List[str] = []
    phones: List[str] = []
    emails: List[str] = []
    urls: List[str] = []
    image: Optional[str] = None
    cdn_image: Optional[str] = None
    jurisdiction_ocdid: str


class SubmittedPersonRecord(PersonBase):
    """One person record a human submitted. The validators below normalise as well as check."""

    label: str = ""
    labels: List[str] = []
    division_ocdid: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    role_id: Optional[str] = None
    unmatched_text: List[str] = []
    source_urls: List[str]
    updated_at: str
    # A reviewer's pick. Never set by the pipeline, which reports labels and nothing else.
    post_id: Optional[str] = None

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v):
        if v is None:
            return v
        patterns = [r"^\d{4}$", r"^\d{4}-\d{2}$", r"^\d{4}-\d{2}-\d{2}$"]
        if not any(re.match(p, v) for p in patterns):
            raise ValueError(
                "Start date must be in format YYYY, YYYY-MM, or YYYY-MM-DD"
            )
        return v

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v):
        if v is None:
            return v
        patterns = [r"^\d{4}$", r"^\d{4}-\d{2}$", r"^\d{4}-\d{2}-\d{2}$"]
        if not any(re.match(p, v) for p in patterns):
            raise ValueError("End date must be in format YYYY, YYYY-MM, or YYYY-MM-DD")
        return v

    @field_validator("phones")
    @classmethod
    def validate_phones(cls, v):
        # accept any layout and canonicalize to '(XXX) XXX-XXXX'; reject the truly invalid
        normalized = []
        for phone in v:
            if not phone or not phone.strip():
                continue
            canonical = normalize_phone_number(phone)
            if not canonical:
                raise ValueError(f"Invalid phone number: '{phone}'")
            normalized.append(canonical)
        return normalized

    @field_validator("emails")
    @classmethod
    def validate_emails(cls, v):
        for email in v:
            if not is_valid_email(email):
                raise ValueError(
                    f"Email must be in format 'anything@anything', got: '{email}'"
                )
        return v

    @field_validator("urls", "source_urls")
    @classmethod
    def validate_urls(cls, v):
        cleaned = []
        for url in v:
            if not url or not url.strip():
                continue
            if not url.startswith(("http://", "https://")):
                raise ValueError(
                    f"Website must start with 'http://' or 'https://', got: '{url}'"
                )
            if not is_web_url(url):
                raise ValueError(
                    f"Website must be a valid URL with a domain, got: '{url}'"
                )
            cleaned.append(url)
        return cleaned

    @field_validator("updated_at")
    @classmethod
    def validate_updated_at(cls, v):
        datetime_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$"
        if not re.match(datetime_pattern, v):
            expected_format = datetime.now(timezone.utc).isoformat(timespec="seconds")
            raise ValueError(
                f"DateTime must be in format '{expected_format}', got: '{v}'"
            )
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError(f"Invalid datetime value: '{v}'")
        return v

    @field_validator("source_urls")
    @classmethod
    def validate_source_urls(cls, v):
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(
                    f"Source URL must start with 'http://' or 'https://', got: '{url}'"
                )
            if not is_web_url(url):
                raise ValueError(
                    f"Source URL must be a valid URL with a domain, got: '{url}'"
                )
        return v


# An `image` still pointing at the file the scrape downloaded, before anyone resolved it.
LOCAL_IMAGE_PREFIX = "local://"


class ExtractedPersonRecord(BaseModel):
    """One person as a page yielded them, before anyone says where the page was.

    Deliberately holds nothing the extractor could not have read off the page. It is passed
    to the model as a structured-output schema, so a `source_url` here would be an invitation
    to invent a plausible one — provenance comes from whoever genuinely has it.

    One record per label, verbatim. Not decomposed into role + designation: cp.org owns that,
    and splitting here loses which went with which.
    """

    name: str
    label: str

    phone: Optional[str] = None
    email: Optional[str] = None
    url: Optional[str] = None

    start_date: Optional[str] = None
    end_date: Optional[str] = None
    image: Optional[str] = None


class PersonSourceRecord(ExtractedPersonRecord):
    """One sighting, stamped with the page it came from.

    The unit that crosses the pipeline/cp.org boundary. Several may describe one person —
    reconciling them is cp.org's job, because that is where the taxonomy, the role priorities
    and the known people live.

    No "LLM" in the name on purpose: the pipeline could swap extraction for a DOM parser and
    the boundary contract should not change, or become a lie.
    """

    source_url: str


class Post(BaseModel):
    """The `posts` row, plus the label composed on read. No `_is_verified` — that is per-query."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    jurisdiction_ocdid: str
    organization_id: str
    role_id: str
    division_ocdid: str
    label: str
    headcount: int = Field(default=1, alias="_headcount")
    is_tracked: bool = Field(default=True, alias="_is_tracked")


class Membership(BaseModel):
    """One open membership, as `PERSON_MEMBERSHIPS` projects it. Narrower than the frontend's
    `Membership`, which the posts-list page needs for `decompose`."""

    # memberships
    post_id: str
    label: Optional[str] = None
    source_labels: List[str] = []
    designations: List[str] = []
    unmatched_text: List[str] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    # posts, and roles, through the join
    role_id: str
    division_ocdid: str
    role_label: str

    # composed by `database.people.labelled` — no column holds it
    post_label: str = ""


class DerivedPerson(PersonBase):
    """One person's sightings combined — what `people_derivation` produces.

    Not a people row: nothing is written yet, and no post has been derived, so it carries the
    raw `labels` and no membership.
    """

    source_urls: List[str] = []
    updated_at: Optional[str] = None
    # Verbatim, one per office. Decomposition into role + division + unmatched happens later,
    # in `derive_roles`.
    labels: List[str] = []


class Person(PersonBase):
    """The people row and its open memberships.

    `GET /people` returns this model directly, so a key `PERSON_JSON` projects but this does
    not declare is dropped from the response rather than rejected.
    """

    source_urls: List[str] = []
    updated_at: Optional[str] = None
    memberships: List[Membership] = []


class OpenStatesMembership(BaseModel):
    """Exactly the keys `PERSON_MEMBERSHIPS` projects. Not `Membership`: its `post_label` would
    add a null key to every membership in every published file."""

    post_id: str
    role_id: str
    role_label: Optional[str] = None
    division_ocdid: Optional[str] = None
    label: Optional[str] = None
    source_labels: List[str] = []
    designations: List[str] = []
    unmatched_text: List[str] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class OpenStatesPersonRecord(PersonBase):
    """One person as written to open-data. The keys of `PERSON_JSON`; a key it does not declare
    is dropped from the published file."""

    source_urls: List[str] = []
    updated_at: Optional[str] = None
    labels: List[str] = []
    division_ocdid: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    memberships: List[OpenStatesMembership] = []


class JobConfig(BaseModel):
    max_pages: int
    pipeline_run_cost_limit: Decimal  # in USD


class JurisdictionLevel(StrEnum):
    # Values mirror open-data's data_source/<state>/<level>/ directory names, which are
    # also stored verbatim in jurisdictions.level.
    STATE = "state"
    COUNTIES = "counties"
    LOCAL = "local"


class JurisdictionId(BaseModel):
    country: str
    state: str
    county: Optional[str] = None
    place_label: str = "place"
    # State-level and county-level OCDIDs have no place component.
    place: Optional[str] = None
    jurisdiction_type: str

    @property
    def level(self) -> JurisdictionLevel:
        # A place under a county is still local — the county segment locates it, it does
        # not make it a county. Derived, not stored, so it cannot drift from the parts.
        if self.place:
            return JurisdictionLevel.LOCAL
        if self.county:
            return JurisdictionLevel.COUNTIES
        return JurisdictionLevel.STATE


class JurisdictionEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    url: Optional[str] = None
    comments: List[str] = []


class JurisdictionsFile(BaseModel):
    model_config = ConfigDict(extra="allow")

    jurisdictions: List[JurisdictionEntry] = []


class PipelineRunConfig(BaseModel):
    # open-data reads this field from pipeline_run_context.json to detect domain drift
    # and update jurisdictions.yml (scripts/github_actions/update_jurisdiction_url.py)
    url: str
    name: Optional[str] = None
    source_urls: Optional[List[str]] = None


class IssueCode(str, Enum):
    # A reviewer-facing data-quality issue. Each value is emitted by the
    # `_check_*` named after it in review_utils (build_review_summary).
    # Named for what was observed, not for what it means: the scrape did not find someone we
    # expected, or found someone we did not. Whether that is a departure or an arrival is the
    # reviewer's call, so the code must not make it for them.
    ABSENT_PERSON = "absent_person"
    NEW_PERSON = "new_person"
    MOVED_PERSON = "moved_person"
    # A reviewer picked a post and the scrape now derives a different one. Observed, not
    # interpreted: whether the pick is still right or the parser has learned something is
    # exactly what the reviewer is being asked.
    DISPUTED_POST = "disputed_post"
    TOO_FEW_PEOPLE = "too_few_people"
    DUPLICATE_UNIQUE_ROLE = "duplicate_unique_role"
    DIVISION_NUMBERING_GAP = "division_numbering_gap"
    # The exception to the comment above: computed from stored posts at read time, not by a
    # `_check_*` here, because it is about an office rather than about a person and every
    # check in this module counts people.
    UNVERIFIED_POST = "unverified_post"


# Two packages write this anchor and the frontend reads it; a typo un-anchors an issue silently.
POST_FIELD = "post_id"


class Issue(BaseModel):
    code: IssueCode
    message: str
    # people this issue lands on; empty for list-level issues (absent_person,
    # division_numbering_gap, too_few_people). `field` anchors it to a cell, e.g.
    # "post_id" — absent for whole-row / list-level issues.
    person_ids: List[str] = []
    field: Optional[str] = None


class RoleStatus(str, Enum):
    ACTIVE = "active"
    CANDIDATE = "candidate"
    # "this label is not a role" — an exclusion the matcher must still see in
    # order to knowingly drop the label. Not the same as inactive.
    EXCLUDED = "excluded"
    # what removal sets. Not matched at all; the row survives so seat history
    # does.
    INACTIVE = "inactive"


class RoleAliasStatus(str, Enum):
    ACTIVE = "active"
    # submitted but unapproved — stored, never matched.
    CANDIDATE = "candidate"


class Role(BaseModel):
    # id is a slug ("council-member"), not a uuid — stable identity, immutable
    # through a label rename. label is display only.
    id: str
    label: str
    # not optional: the column is NOT NULL, and `get_role_configs` filters on
    # this, so a None would silently decide whether the role matches.
    status: RoleStatus = RoleStatus.ACTIVE
    is_unique: bool | None = None
    priority: int | None = None
    aliases: List[str] = []


class RoleConfig(BaseModel):
    roles: List[Role] = []
