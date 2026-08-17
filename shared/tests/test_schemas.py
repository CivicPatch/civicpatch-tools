import pytest
from pydantic import ValidationError

from shared.schemas import Issue, IssueCode, JurisdictionLevel, Official
from shared.utils.id_utils import parse_jurisdiction_ocdid


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


class TestIssue:
    def test_row_anchored_issue(self):
        issue = Issue(
            code=IssueCode.DUPLICATE_UNIQUE_ROLE,
            message="Role 'mayor' held by multiple officials",
            person_ids=["abc", "def"],
            field="office.name",
        )
        assert issue.code is IssueCode.DUPLICATE_UNIQUE_ROLE
        assert issue.person_ids == ["abc", "def"]
        assert issue.field == "office.name"

    def test_list_level_defaults(self):
        issue = Issue(code=IssueCode.TOO_FEW_PEOPLE, message="Only 2 people found")
        assert issue.person_ids == []
        assert issue.field is None

    def test_code_serializes_to_snake_case_string(self):
        # It rides in review_json (jsonb) → the code must serialize as a plain string.
        dumped = Issue(code=IssueCode.ABSENT_OFFICIAL, message="x").model_dump(mode="json")
        assert dumped["code"] == "absent_official"

    def test_round_trips_through_serialization(self):
        issue = Issue(code=IssueCode.NEW_OFFICIAL, message="Not previously known: John Doe", person_ids=["xyz"])
        assert Issue(**issue.model_dump()) == issue
        assert Issue(**issue.model_dump(mode="json")) == issue

    def test_rejects_unknown_code(self):
        with pytest.raises(ValidationError):
            Issue(code="not_a_real_code", message="x")


class TestJurisdictionLevel:
    """JurisdictionId.level — which data_source/<state>/<level>/ slice an ocdid belongs to.

    Derived from county/place rather than stored, so it cannot drift from the parts it
    is computed from.
    """

    def test_place_under_state_is_local(self):
        parsed = parse_jurisdiction_ocdid(
            "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
        )
        assert parsed.level is JurisdictionLevel.LOCAL

    def test_place_under_county_is_still_local(self):
        # The county segment locates the place; it does not make it a county.
        parsed = parse_jurisdiction_ocdid(
            "ocd-jurisdiction/country:us/state:mi/county:calhoun/place:albion/government"
        )
        assert parsed.level is JurisdictionLevel.LOCAL

    def test_county_without_a_place_is_counties(self):
        parsed = parse_jurisdiction_ocdid(
            "ocd-jurisdiction/country:us/state:wa/county:king/government"
        )
        assert parsed.level is JurisdictionLevel.COUNTIES

    def test_state_only_is_state(self):
        parsed = parse_jurisdiction_ocdid(
            "ocd-jurisdiction/country:us/state:wa/government"
        )
        assert parsed.level is JurisdictionLevel.STATE

    def test_level_is_the_open_data_directory_name(self):
        # Interpolated straight into a repo path, so the string value is the contract.
        assert f"{JurisdictionLevel.COUNTIES}" == "counties"
