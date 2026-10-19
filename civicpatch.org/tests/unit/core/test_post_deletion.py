import pytest
from shared.schemas import Post

from core.post_deletion import merge_refusal, with_holder_names

pytestmark = pytest.mark.unit

SEATTLE = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
BASE = "ocd-division/country:us/state:wa/place:seattle"


def post(id: str, organization: str, role: str = "mayor", division: str = BASE, jurisdiction: str = SEATTLE) -> Post:
    return Post(
        id=id,
        jurisdiction_ocdid=jurisdiction,
        organization_id=organization,
        role_id=role,
        division_ocdid=division,
        label="Mayor",
        role_label="Mayor",
    )


COUNCIL_MAYOR = post("p1", "council")


def test_the_same_office_in_another_organization_can_take_it():
    assert merge_refusal(COUNCIL_MAYOR, post("p2", "office-of-the-mayor")) is None


@pytest.mark.parametrize(
    "into",
    [
        COUNCIL_MAYOR,
        post("p2", "office-of-the-mayor", jurisdiction="ocd-jurisdiction/country:us/state:wa/place:tacoma/government"),
        post("p2", "council", division=f"{BASE}/ward:1"),
        post("p2", "office-of-the-mayor", role="clerk"),
        post("p2", "office-of-the-mayor", division=f"{BASE}/ward:1"),
    ],
    ids=["itself", "another jurisdiction", "same organization", "another role", "another division"],
)
def test_anything_else_is_refused_with_a_reason(into):
    assert merge_refusal(COUNCIL_MAYOR, into)


def test_each_post_gets_who_holds_or_held_it():
    organizations = [{"id": "council", "posts": [{"id": "held"}, {"id": "empty"}]}]

    [organization] = with_holder_names(organizations, {"held": ["Bruce Harrell"]})

    assert organization["posts"] == [
        {"id": "held", "holder_names": ["Bruce Harrell"]},
        {"id": "empty", "holder_names": []},
    ]
