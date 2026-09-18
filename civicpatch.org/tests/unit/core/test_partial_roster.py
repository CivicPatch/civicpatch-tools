"""Pure — a partial source's roster laid over the published one. No mocks."""

import pytest

from core.people_roster import partial_roster
from shared.schemas import POST_FIELD

_PUBLISHED = {
    "id": "p1",
    "name": "Victor Linares",
    "emails": ["vlinares@covinaca.gov"],
    "phones": ["(626) 384-5410"],
    "urls": ["https://covinaca.gov/our-city/government/city-council/"],
    "labels": ["Council Member, District 3"],
    "memberships": [{"post_id": "post-district-3"}],
}


def _proposed(**fields):
    return {"id": "p1", "name": "Victor Linares", "emails": [], "phones": [], "urls": [],
            "labels": ["Council Member, District 3"], **fields}


@pytest.mark.unit
def test_a_blank_cell_keeps_the_published_value():
    [person] = partial_roster([_proposed()], [_PUBLISHED])

    assert person["emails"] == ["vlinares@covinaca.gov"]
    assert person["phones"] == ["(626) 384-5410"]
    assert person["urls"] == ["https://covinaca.gov/our-city/government/city-council/"]


@pytest.mark.unit
def test_a_filled_cell_is_what_the_source_says():
    [person] = partial_roster([_proposed(emails=["new@covinaca.gov"])], [_PUBLISHED])

    assert person["emails"] == ["new@covinaca.gov"]


@pytest.mark.unit
def test_a_blank_label_keeps_the_current_labels_and_posts():
    [person] = partial_roster([_proposed(labels=[""])], [_PUBLISHED])

    assert person["labels"] == ["Council Member, District 3"]
    assert person[POST_FIELD] == ["post-district-3"]


@pytest.mark.unit
def test_a_stated_label_is_not_pinned_to_the_current_post():
    """A new title is a real move, so it must derive, not stay where they were."""
    [person] = partial_roster([_proposed(labels=["Mayor"])], [_PUBLISHED])

    assert person["labels"] == ["Mayor"]
    assert POST_FIELD not in person


@pytest.mark.unit
def test_someone_not_published_has_nothing_to_keep():
    newcomer = {"id": "p9", "name": "Nobody Yet", "emails": [], "labels": []}

    assert partial_roster([newcomer], [_PUBLISHED]) == [newcomer]
