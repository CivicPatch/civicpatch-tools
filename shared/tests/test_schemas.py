import pytest
from pydantic import ValidationError

from shared.schemas import Official


def make_official(**overrides):
    base = dict(
        name="Jane Smith",
        office={"name": "Council Member"},
        jurisdiction_ocdid="ocd-jurisdiction/country:us/state:co/place:denver/government",
        source_urls=["https://denvergov.org/council"],
        updated_at="2025-06-27T19:43:55+00:00",
    )
    base.update(overrides)
    return Official(**base)


class TestPhoneValidation:
    def test_canonicalizes_any_layout(self):
        official = make_official(phones=["7203377701", "720-337-7701", "(720) 337-7701"])
        assert official.phones == ["(720) 337-7701", "(720) 337-7701", "(720) 337-7701"]

    def test_drops_blanks(self):
        official = make_official(phones=["", "   ", "7203377701"])
        assert official.phones == ["(720) 337-7701"]

    def test_rejects_garbage(self):
        with pytest.raises(ValidationError):
            make_official(phones=["not a phone"])


class TestUrlValidation:
    def test_accepts_valid_http_urls(self):
        official = make_official(urls=["https://example.com/path"])
        assert official.urls == ["https://example.com/path"]

    def test_rejects_scheme_less(self):
        with pytest.raises(ValidationError):
            make_official(urls=["example.com"])

    def test_rejects_no_domain(self):
        with pytest.raises(ValidationError):
            make_official(urls=["https://nodot"])

    def test_source_urls_validated_too(self):
        with pytest.raises(ValidationError):
            make_official(source_urls=["garbage"])

    def test_drops_blank_urls(self):
        official = make_official(urls=["", "https://example.com"])
        assert official.urls == ["https://example.com"]
