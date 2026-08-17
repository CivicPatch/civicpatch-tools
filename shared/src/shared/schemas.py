import re
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum, StrEnum
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, field_validator
from shared.utils.phone_utils import normalize_phone_number


class Office(BaseModel):
    name: str
    division_ocdid: Optional[str] = None


class Official(BaseModel):
    name: str
    other_names: List[str] = []
    phones: List[str] = []
    emails: List[str] = []
    urls: List[str] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    office: Office
    image: Optional[str] = None
    jurisdiction_ocdid: str
    cdn_image: Optional[str] = None
    source_urls: List[str]
    updated_at: str
    id: str = ""

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
            try:
                canonical = normalize_phone_number(phone)
            except ValueError as e:
                raise ValueError(
                    f"Invalid phone number: '{phone}' (phonenumbers failed to parse)"
                ) from e
            if not canonical:
                raise ValueError(f"Invalid phone number: '{phone}'")
            normalized.append(canonical)
        return normalized

    @field_validator("emails")
    @classmethod
    def validate_emails(cls, v):
        email_pattern = r"^[^@]+@[^@]+$"
        for email in v:
            if not re.match(email_pattern, email):
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
            parsed = urlparse(url)
            if not parsed.netloc or "." not in parsed.netloc:
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
            parsed = urlparse(url)
            if not parsed.netloc or "." not in parsed.netloc:
                raise ValueError(
                    f"Source URL must be a valid URL with a domain, got: '{url}'"
                )
        return v


class Person(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    other_names: List[str] = []
    # Raw labels, one per office, verbatim from the page. Decomposition into role +
    # division + unmatched happens in cp.org, not here.
    labels: List[str] = []
    phones: List[str] = []
    emails: List[str] = []
    urls: List[str] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    image: Optional[str] = None
    jurisdiction_ocdid: str
    cdn_image: Optional[str] = None
    source_urls: List[str] = []
    updated_at: Optional[str] = None


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
    MISSING_OFFICIAL = "missing_official"
    EXTRA_OFFICIAL = "extra_official"
    TOO_FEW_PEOPLE = "too_few_people"
    DUPLICATE_UNIQUE_ROLE = "duplicate_unique_role"
    DIVISION_NUMBERING_GAP = "division_numbering_gap"


class Issue(BaseModel):
    code: IssueCode
    message: str
    # people this issue lands on; empty for list-level issues (missing_official,
    # division_numbering_gap, too_few_people). `field` anchors it to a cell, e.g.
    # "office.name" — absent for whole-row / list-level issues.
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
