"""Review cards keep their sources for everyone; the debug links are admins' only."""

from datetime import datetime, timezone

import pytest

from routers.api.review_cards import _for_viewer
from schemas.common import UserRole
from schemas.review_cards import ReviewCard, ReviewSource

pytestmark = pytest.mark.unit

_CACHED_AT = datetime(2026, 10, 23, tzinfo=timezone.utc)


def _card() -> ReviewCard:
    return ReviewCard.model_construct(
        changeset_id="changeset-1",
        sources=[
            ReviewSource(
                url="https://seattle.gov/council",
                markdown="m",
                html="h",
                cached_at=_CACHED_AT,
                is_cached_by_this_scrape=True,
            )
        ],
    )


def test_an_admin_gets_the_debug_links():
    [card] = _for_viewer([_card()], UserRole.ADMINS.value)

    assert card.sources[0].markdown == "m"
    assert card.sources[0].html == "h"


def test_a_reviewer_keeps_the_source_but_not_its_debug_links():
    [card] = _for_viewer([_card()], UserRole.MAINTAINERS.value)

    source = card.sources[0]
    assert source.url == "https://seattle.gov/council"
    assert (source.markdown, source.html) == (None, None)
    # Everyone learns how old the copy is and whether this scrape read it; only the links are admins'.
    assert (source.cached_at, source.is_cached_by_this_scrape) == (_CACHED_AT, True)
