from unittest.mock import MagicMock

import pytest
from runners.people_collector.schemas import LLMPersonRecord
from runners.people_collector.steps.step_05_merge_records_within_llm.normalize import (
    normalize_record,
)
from shared.utils.config_utils import RoleConfig
from utils.taxonomy import build_taxonomy

pytestmark = pytest.mark.unit

EMPTY_TAXONOMY = build_taxonomy(RoleConfig(roles=[]))


def _normalize(record: LLMPersonRecord) -> LLMPersonRecord:
    return normalize_record(MagicMock(), EMPTY_TAXONOMY, record)


def test_normalize_record_strips_whitespace_from_email():
    record = LLMPersonRecord(
        name="John Doe",
        roles=["mayor"],
        phone=None,
        email="john @example.com",
        url=None,
        designations=[],
        source_url="test",
    )
    assert _normalize(record).email == "john@example.com"


def test_normalize_record_strips_internal_whitespace_from_email():
    record = LLMPersonRecord(
        name="John Doe",
        roles=["mayor"],
        phone=None,
        email="john@ example .com",
        url=None,
        designations=[],
        source_url="test",
    )
    assert _normalize(record).email == "john@example.com"


def test_normalize_record_moves_url_from_email_to_url_when_url_empty():
    record = LLMPersonRecord(
        name="John Doe",
        roles=["mayor"],
        phone=None,
        email="https://example.com/contact",
        url=None,
        designations=[],
        source_url="test",
    )
    result = _normalize(record)
    assert result.email is None
    assert result.url == "https://example.com/contact"


def test_normalize_record_clears_url_from_email_when_url_already_set():
    record = LLMPersonRecord(
        name="John Doe",
        roles=["mayor"],
        phone=None,
        email="https://example.com/contact-form",
        url="https://example.com/bio",
        designations=[],
        source_url="test",
    )
    result = _normalize(record)
    assert result.email is None
    assert result.url == "https://example.com/bio"


def test_normalize_record_with_compound_phone_takes_first():
    record = LLMPersonRecord(
        name="Alice Boroughman",
        roles=["mayor"],
        phone="856-358-2509 or 856-358-4010 Ext. 112",
        email=None,
        url=None,
        designations=[],
        source_url="http://example.com",
    )
    assert _normalize(record).phone == "(856) 358-2509"
