from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

KNOWN_PLACE_KEYS = ["place", "special_district"]


class RouteCategory(str, Enum):
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    TEAM_REQUIRED = "team_required"
    SERVICE = "service"


class ReviewMode(str, Enum):
    BASELINE = "baseline"      # first capture for a jurisdiction; nothing to diff against
    RECONCILE = "reconcile"    # subsequent scrape; old<->new pairing is meaningful

    @classmethod
    def for_scrape(cls, scraped_at: datetime | None) -> "ReviewMode":
        return cls.BASELINE if scraped_at is None else cls.RECONCILE


class UserRole(str, Enum):
    DEFAULT = "default"
    CONTRIBUTORS = "contributors"
    MAINTAINERS = "maintainers"
    ADMINS = "admins"


# Trust ladder: a user holds one level; permissions cascade downward.
# admins > maintainers > contributors > default. Higher rank = more powers.
_ROLE_RANK: dict[str, int] = {
    UserRole.DEFAULT.value: 0,
    UserRole.CONTRIBUTORS.value: 1,
    UserRole.MAINTAINERS.value: 2,
    UserRole.ADMINS.value: 3,
}


def role_rank(role: str | None) -> int:
    if role is None:
        return -1  # unauthenticated: below default
    return _ROLE_RANK.get(role, 0)


def has_at_least(user_role: str | None, required: UserRole) -> bool:
    return role_rank(user_role) >= role_rank(required.value)


class Jurisdiction(BaseModel):
    id: str
    name: str
    url: str | None


class StateJurisdictionSets(BaseModel):
    total: set[str]  # all current jurisdictions in the state
    scrapeable: set[str]  # subset with a url
    covered_fresh: set[str]  # scrapeable + has officials + scraped within the freshness window
    covered_stale: set[str]  # scrapeable + has officials but aging (or never-stamped)


class Identity(BaseModel):
    type: str  # "session", "service_key", "user_key"
    provider: str
    provider_user_id: str
    email: str | None
    # role is the trust level for human user identities (cookie/user_key).
    # `service_api_key` identities have role=None — they bypass the team check
    # via `require_route_access`'s type-based short-circuit, not via the ladder.
    role: str | None = None
    user_id: str | None = None
    display_name: str | None = None


class UserWithRole(BaseModel):
    id: str
    email: str | None
    display_name: str | None
    provider: str
    provider_user_id: str
    role: str
    last_login_at: str | None = None


class SetRoleRequest(BaseModel):
    role: UserRole


class InviteUserRequest(BaseModel):
    email: str


class ReportReviewIssueRequest(BaseModel):
    description: str = Field(min_length=1, max_length=10000)


class PendingInvite(BaseModel):
    id: str
    email: str | None
    invited_at: str | None


class RequestOtpRequest(BaseModel):
    email: str


class VerifyOtpRequest(BaseModel):
    email: str
    code: str


class InFlightEntryType(str, Enum):
    """Which table the entry came from, and therefore how to read its `id`."""

    PIPELINE_RUN = "pipeline_run"
    CHANGESET = "changeset"


class InFlightEntry(BaseModel):
    """One thing this jurisdiction is still waiting on: an attempt, or a proposal.

    `entry_type` says which table `id` is from. `is_running` cannot — it is true in both, since
    between ingest and the terminal report a changeset exists and its run is still going.
    """

    id: str
    entry_type: InFlightEntryType
    created_at: Optional[str]
    # `updated_at` — when the source was read. What a run's elapsed time is measured against.
    updated_at: Optional[str]
    kind: Optional[str]
    change_url: Optional[str]
    pipeline_run_status: Optional[str]
    pipeline_run_progress: Optional[int]
    is_running: bool
    awaiting_review: bool


class JurisdictionInFlight(BaseModel):
    """What the jurisdiction page needs without reading the whole history.

    `last_published_at` is the publish's own timestamp, never `jurisdictions.scraped_at` — that
    column is the run's `created_at` and is written only for scrapes, so it dates the machine
    rather than the decision and ignores imports and edits entirely.
    """

    in_flight: list[InFlightEntry]
    last_published_at: Optional[str]
    total_changesets: int
