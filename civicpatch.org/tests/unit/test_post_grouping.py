"""Unit tests for the roster-screen shape (core.post_grouping).

Pure — no database. The SQL behind it is covered by the integration tests.
"""

import pytest

from core.post_grouping import group_by_organization


def _org(id_: str, name: str) -> dict:
    return {"id": id_, "name": name, "sort_order": 0}


def _post(organization_id: str, role_id: str, division: str = "…/place:zz") -> dict:
    return {
        # Identity is the triple, per posts_identity_uq — two bodies can hold the same
        # role at the same division.
        "id": f"post-{organization_id}-{role_id}-{division}",
        "organization_id": organization_id,
        "role_id": role_id,
        "division_ocdid": division,
        "label": None,
        "_headcount": 1,
        "_is_verified": True,
        "holders": 1,
    }


@pytest.mark.unit
def test_posts_nest_under_their_own_organization():
    grouped = group_by_organization(
        [_org("a", "City Council"), _org("b", "Planning Board")],
        [_post("a", "council-member"), _post("b", "commissioner")],
    )

    assert [o["name"] for o in grouped] == ["City Council", "Planning Board"]
    assert [p["role_id"] for p in grouped[0]["posts"]] == ["council-member"]
    assert [p["role_id"] for p in grouped[1]["posts"]] == ["commissioner"]


@pytest.mark.unit
def test_an_organization_with_no_posts_is_kept():
    """A body that exists with nothing in it is a real state, not an empty result to hide."""
    grouped = group_by_organization([_org("a", "City Council")], [])

    assert len(grouped) == 1
    assert grouped[0]["posts"] == []


@pytest.mark.unit
def test_the_database_ordering_is_preserved():
    """`posts.list_for_jurisdiction` orders by role then division; grouping must not resort."""
    posts = [
        _post("a", "council-member", "…/district:1"),
        _post("a", "council-member", "…/district:2"),
        _post("a", "mayor"),
    ]
    grouped = group_by_organization([_org("a", "City Council")], posts)

    assert [p["division_ocdid"] for p in grouped[0]["posts"]] == [
        "…/district:1",
        "…/district:2",
        "…/place:zz",
    ]


@pytest.mark.unit
def test_an_orphaned_post_does_not_vanish_or_raise():
    """A post whose organization is missing is dropped from the response, not crashed on."""
    grouped = group_by_organization([_org("a", "City Council")], [_post("gone", "mayor")])

    assert grouped == [{"id": "a", "name": "City Council", "sort_order": 0, "posts": []}]
