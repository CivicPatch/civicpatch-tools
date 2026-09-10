import pytest

from core.people_edits import source_values_overridden, with_asserted_values
from schemas.assertions import AssertionKind


def _asserted(field: str, accept=(), reject=()):
    return {field: {AssertionKind.ACCEPT: list(accept), AssertionKind.REJECT: list(reject)}}


@pytest.mark.unit
def test_a_person_nobody_has_looked_at_is_unchanged():
    person = {"name": "Jane Doe", "phones": ["(555) 0001"]}
    assert with_asserted_values(person, {}) == person


@pytest.mark.unit
def test_a_rejected_number_stays_gone_however_often_it_is_scraped():
    """The property the model was chosen for. A reviewer who deletes a fax number must not have
    to delete it again every week."""
    person = {"phones": ["(555) 0001", "(555) 0002"]}
    asserted = _asserted("phones", reject=["(555) 0001"])
    assert with_asserted_values(person, asserted)["phones"] == ["(555) 0002"]


@pytest.mark.unit
def test_a_number_nobody_rejected_still_arrives():
    """A rejection suppresses one value, never the field — so a genuinely new answer reaches a
    reviewer rather than being silently overridden by an older judgement."""
    person = {"phones": ["(555) 0001", "(555) 9999"]}
    asserted = _asserted("phones", reject=["(555) 0001"])
    assert with_asserted_values(person, asserted)["phones"] == ["(555) 9999"]


@pytest.mark.unit
def test_an_accepted_value_the_scrape_never_found_is_pinned():
    person = {"phones": []}
    asserted = _asserted("phones", accept=["(555) 8888"])
    assert with_asserted_values(person, asserted)["phones"] == ["(555) 8888"]


@pytest.mark.unit
def test_scraped_order_comes_first_and_nothing_is_duplicated():
    """Set algebra has no order of its own, and the source's is the only one anybody chose."""
    person = {"phones": ["(555) 0001", "(555) 0002"]}
    asserted = _asserted("phones", accept=["(555) 0002", "(555) 8888"])
    assert with_asserted_values(person, asserted)["phones"] == [
        "(555) 0001",
        "(555) 0002",
        "(555) 8888",
    ]


@pytest.mark.unit
def test_rejecting_beats_accepting_the_same_value():
    """Both can exist: one row per value per kind, and no constraint spans the two."""
    person = {"phones": ["(555) 0001"]}
    asserted = _asserted("phones", accept=["(555) 0001"], reject=["(555) 0001"])
    assert with_asserted_values(person, asserted)["phones"] == []


@pytest.mark.unit
def test_a_scalar_is_replaced_not_unioned():
    person = {"name": "Jane Doe"}
    asserted = _asserted("name", accept=["Jane Smith"])
    assert with_asserted_values(person, asserted)["name"] == "Jane Smith"


@pytest.mark.unit
def test_a_rejected_scalar_with_no_replacement_is_emptied():
    person = {"image": "https://x.gov/wrong.png"}
    asserted = _asserted("image", reject=["https://x.gov/wrong.png"])
    assert with_asserted_values(person, asserted)["image"] is None


@pytest.mark.unit
def test_a_field_nobody_can_edit_is_left_alone():
    """`cdn_image` is written by image promotion at publish, so a claim about it would be
    overwritten and read as the system ignoring somebody."""
    person = {"cdn_image": "https://cdn/x.png"}
    asserted = _asserted("cdn_image", accept=["https://cdn/other.png"])
    assert with_asserted_values(person, asserted)["cdn_image"] == "https://cdn/x.png"


# ── what the lock hides ───────────────────────────────────────────────────────


@pytest.mark.unit
def test_nothing_is_hidden_when_no_assertion_moved_a_value():
    """A lock over a value the scrape agrees with has nothing to disclose, so it earns no
    hover — an accept that merely confirms what was scraped discloses nothing either way."""
    person = {"name": "Jane Doe", "phones": ["(555) 0001"]}
    asserted = _asserted("phones", accept=["(555) 0001"])

    assert source_values_overridden(person, asserted) == {}


@pytest.mark.unit
def test_an_accept_that_replaced_the_scraped_value_discloses_it():
    person = {"name": "Jane Doe", "phones": ["(555) 0001"]}
    asserted = _asserted("phones", accept=["(555) 9999"])

    assert source_values_overridden(person, asserted) == {"phones": ["(555) 0001"]}


@pytest.mark.unit
def test_a_reject_discloses_what_it_suppressed():
    """The reviewer sees an empty field and a lock; the hover is the only place the deleted fax
    number still exists on screen."""
    person = {"phones": ["(555) 0001"]}
    asserted = _asserted("phones", reject=["(555) 0001"])

    assert source_values_overridden(person, asserted) == {"phones": ["(555) 0001"]}


@pytest.mark.unit
def test_a_field_outside_the_editable_set_is_never_disclosed():
    """The same guard `with_asserted_values` applies before overlaying: a field it will not
    overlay cannot have been overridden, so there is nothing behind the lock.

    `memberships` rather than `source_urls` — the latter reads like the obvious example and is
    not one, because it *is* editable. `NOT_ASSERTABLE` is a separate guard on the edit path."""
    person = {"memberships": [{"post_id": "post-1"}]}
    asserted = _asserted("memberships", accept=[{"post_id": "post-2"}])

    assert source_values_overridden(person, asserted) == {}
