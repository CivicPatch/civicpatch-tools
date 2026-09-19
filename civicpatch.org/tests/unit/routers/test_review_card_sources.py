"""Review cards keep their sources for everyone; the debug links are admins' only."""

import pytest

from routers.api.review_cards import _for_viewer
from schemas.common import UserRole
from schemas.review_cards import ReviewCard, ReviewSource

pytestmark = pytest.mark.unit


def _card() -> ReviewCard:
    return ReviewCard.model_construct(
        changeset_id="changeset-1",
        sources=[ReviewSource(url="https://seattle.gov/council", markdown="m", html="h")],
    )


def test_an_admin_gets_the_debug_links():
    [card] = _for_viewer([_card()], UserRole.ADMINS.value)

    assert card.sources[0].markdown == "m"
    assert card.sources[0].html == "h"


def test_a_reviewer_keeps_the_source_but_not_its_debug_links():
    [card] = _for_viewer([_card()], UserRole.MAINTAINERS.value)

    assert card.sources[0].url == "https://seattle.gov/council"
    assert (card.sources[0].markdown, card.sources[0].html) == (None, None)
