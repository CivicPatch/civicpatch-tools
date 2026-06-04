import re
from datetime import datetime, timezone
from decimal import Decimal
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
            raise ValueError("Start date must be in format YYYY, YYYY-MM, or YYYY-MM-DD")
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
                raise ValueError(f"Invalid phone number: '{phone}' (phonenumbers failed to parse)") from e
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
                raise ValueError(f"Email must be in format 'anything@anything', got: '{email}'")
        return v

    @field_validator("urls", "source_urls")
    @classmethod
    def validate_urls(cls, v):
        cleaned = []
        for url in v:
            if not url or not url.strip():
                continue
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Website must start with 'http://' or 'https://', got: '{url}'")
            parsed = urlparse(url)
            if not parsed.netloc or "." not in parsed.netloc:
                raise ValueError(f"Website must be a valid URL with a domain, got: '{url}'")
            cleaned.append(url)
        return cleaned

    @field_validator("updated_at")
    @classmethod
    def validate_updated_at(cls, v):
        datetime_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$"
        if not re.match(datetime_pattern, v):
            expected_format = datetime.now(timezone.utc).isoformat(timespec="seconds")
            raise ValueError(f"DateTime must be in format '{expected_format}', got: '{v}'")
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
                raise ValueError(f"Source URL must start with 'http://' or 'https://', got: '{url}'")
            parsed = urlparse(url)
            if not parsed.netloc or "." not in parsed.netloc:
                raise ValueError(f"Source URL must be a valid URL with a domain, got: '{url}'")
        return v


class Person(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    other_names: List[str] = []
    roles: List[str] = []
    designations: List[str] = []
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


class JurisdictionId(BaseModel):
    country: str
    state: str
    county: Optional[str] = None
    place_label: str = "place"
    # State-level and county-level OCDIDs have no place component.
    place: Optional[str] = None
    jurisdiction_type: str
    output_type: str


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
