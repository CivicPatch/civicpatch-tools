import pytest
from shared.utils import phone_utils


# normalize_first_phone

def test_normalize_first_phone_single_valid():
    assert phone_utils.normalize_first_phone("856-358-2509") == "(856) 358-2509"

def test_normalize_first_phone_compound_or_separator():
    assert phone_utils.normalize_first_phone("856-358-2509 or 856-358-4010 Ext. 112") == "(856) 358-2509"

def test_normalize_first_phone_compound_slash_separator():
    assert phone_utils.normalize_first_phone("856-358-2509 / 856-358-4010") == "(856) 358-2509"

def test_normalize_first_phone_all_invalid_returns_none():
    assert phone_utils.normalize_first_phone("not a phone number") is None

def test_normalize_first_phone_empty_returns_none():
    assert phone_utils.normalize_first_phone("") is None

def test_normalize_first_phone_none_returns_none():
    assert phone_utils.normalize_first_phone(None) is None
