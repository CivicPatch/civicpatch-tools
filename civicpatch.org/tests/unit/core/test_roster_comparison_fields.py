import pytest
from shared.schemas import Role, RoleConfig
from shared.utils.taxonomy import build_taxonomy

from core.roster_comparison_fields import (
    compare_emails,
    compare_phones,
    compare_role,
    compare_start_date,
    compare_urls,
    grade,
)
from schemas.roster_comparisons import FieldLevel

# As open-data's config.yml has it: council and select board posts are all the one `member` role.
TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            Role(id="mayor", label="Mayor", is_unique=True),
            Role(id="vice-mayor", label="Vice Mayor", is_unique=True),
            Role(
                id="member",
                label="Member",
                aliases=["Council Member", "councilmember", "Select Board Member", "selectman"],
            ),
        ]
    )
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("uploaded", "civicpatch", "level"),
    [
        (set(), set(), FieldLevel.BOTH_EMPTY),
        (set(), {"a"}, FieldLevel.UPLOADED_DATA_HAS_NONE),
        ({"a"}, set(), FieldLevel.CIVICPATCH_HAS_NONE),
        ({"a"}, {"a"}, FieldLevel.EQUAL),
        ({"a"}, {"a", "b"}, FieldLevel.CIVICPATCH_HAS_MORE),
        ({"a", "b"}, {"a"}, FieldLevel.UPLOADED_DATA_HAS_MORE),
        ({"a", "b"}, {"a", "c"}, FieldLevel.OVERLAP),
        ({"a"}, {"b"}, FieldLevel.DIFFERS),
    ],
)
def test_grade_puts_two_value_sets_at_one_level(uploaded, civicpatch, level):
    assert grade(uploaded, civicpatch) is level


@pytest.mark.unit
def test_emails_compare_without_case_or_whitespace():
    result = compare_emails([" JDoe@Barre.gov "], ["jdoe@barre.gov", "clerk@barre.gov"])

    assert result.level is FieldLevel.CIVICPATCH_HAS_MORE
    assert result.uploaded == ["jdoe@barre.gov"]


@pytest.mark.unit
def test_one_phone_written_two_ways_is_equal():
    assert compare_phones(["802-555-0134"], ["(802) 555-0134"]).level is FieldLevel.EQUAL


@pytest.mark.unit
def test_a_phone_that_does_not_parse_differs_rather_than_vanishing():
    result = compare_phones(["call the office"], ["(802) 555-0134"])

    assert result.level is FieldLevel.DIFFERS
    assert result.uploaded == ["call the office"]


@pytest.mark.unit
def test_urls_compare_by_canonical_form():
    result = compare_urls(["http://www.barre.gov/council/"], ["https://barre.gov/council"])

    assert result.level is FieldLevel.EQUAL


@pytest.mark.unit
def test_a_start_date_given_on_one_side_only():
    assert compare_start_date("2025-01-01", None).level is FieldLevel.CIVICPATCH_HAS_NONE


@pytest.mark.unit
def test_a_council_member_agrees_with_a_vice_mayor_on_a_member_post():
    result = compare_role("Councilmember", ["member", "vice-mayor"], TAXONOMY)

    assert result.level is FieldLevel.CIVICPATCH_HAS_MORE
    assert result.uploaded == ["Member"]
    assert result.civicpatch == ["Member", "Vice Mayor"]


@pytest.mark.unit
def test_two_aliases_of_one_role_are_equal():
    assert compare_role("Selectman", ["member"], TAXONOMY).level is FieldLevel.EQUAL


@pytest.mark.unit
def test_a_role_civicpatch_does_not_hold_differs():
    assert compare_role("Mayor", ["member"], TAXONOMY).level is FieldLevel.DIFFERS


@pytest.mark.unit
def test_role_text_that_names_no_known_role_is_unknown():
    result = compare_role("Keeper of the Pound", ["member"], TAXONOMY)

    assert result.level is FieldLevel.UNKNOWN
    assert result.uploaded == ["Keeper of the Pound"]


@pytest.mark.unit
def test_no_role_uploaded_is_not_unknown():
    assert compare_role(None, ["member"], TAXONOMY).level is FieldLevel.UPLOADED_DATA_HAS_NONE
