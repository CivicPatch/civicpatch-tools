from unittest.mock import MagicMock

import pytest
from runners.people_collector.schemas import PersonRecord
from runners.people_collector.steps.step_05_merge_records_within_llm.normalize import (
    normalize_record,
)
from shared.schemas import RoleConfig
from shared.utils.taxonomy import build_taxonomy

pytestmark = pytest.mark.unit

EMPTY_TAXONOMY = build_taxonomy(RoleConfig(roles=[]))


def _normalize(record: PersonRecord) -> PersonRecord:
    return normalize_record(MagicMock(), record)


def test_normalize_record_strips_whitespace_from_email():
    record = PersonRecord(
        name="John Doe",
        label="mayor",
        phone=None,
        email="john @example.com",
        url=None,
        source_url="test",
    )
    assert _normalize(record).email == "john@example.com"


def test_normalize_record_strips_internal_whitespace_from_email():
    record = PersonRecord(
        name="John Doe",
        label="mayor",
        phone=None,
        email="john@ example .com",
        url=None,
        source_url="test",
    )
    assert _normalize(record).email == "john@example.com"


def test_normalize_record_moves_url_from_email_to_url_when_url_empty():
    record = PersonRecord(
        name="John Doe",
        label="mayor",
        phone=None,
        email="https://example.com/contact",
        url=None,
        source_url="test",
    )
    result = _normalize(record)
    assert result.email is None
    assert result.url == "https://example.com/contact"


def test_normalize_record_clears_url_from_email_when_url_already_set():
    record = PersonRecord(
        name="John Doe",
        label="mayor",
        phone=None,
        email="https://example.com/contact-form",
        url="https://example.com/bio",
        source_url="test",
    )
    result = _normalize(record)
    assert result.email is None
    assert result.url == "https://example.com/bio"


def test_normalize_record_with_compound_phone_takes_first():
    record = PersonRecord(
        name="Alice Boroughman",
        label="mayor",
        phone="856-358-2509 or 856-358-4010 Ext. 112",
        email=None,
        url=None,
        source_url="http://example.com",
    )
    assert _normalize(record).phone == "(856) 358-2509"
