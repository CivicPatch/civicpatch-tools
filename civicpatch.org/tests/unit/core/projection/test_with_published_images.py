"""A photo is served from the CDN only once its changeset is published; before that, from artifacts."""

from datetime import datetime, timezone

import pytest

from core.projection.facts import Facts, SourceRecord
from core.projection.people import Person
from core.projection.roster import Roster, unpublished_images, with_published_images

pytestmark = pytest.mark.unit

_BUCKET = "civicpatch-artifacts"
_HOST = "https://cdn.civicpatch.org"
UNDER_REVIEW = "bb1ea5d7"
PUBLISHED = "e878a599"
KEN_PHOTO = f"https://{_BUCKET}.civicpatch.org/7a1bd87c/data_source/vt/local/place_johnson_village/images/41a59e57dae5.png"
EMMA_PHOTO = f"https://{_BUCKET}.civicpatch.org/a1da015f/data_source/vt/local/place_burlington/images/bb48ae910586.png"


def record(id: str, changeset_id: str, cdn_image: str | None) -> SourceRecord:
    return SourceRecord(
        id=id,
        changeset_id=changeset_id,
        created_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
        person_id=id,
        organization_id="board",
        name=id,
        label="Trustee",
        source_url="https://example.gov/board",
        cdn_image=cdn_image,
    )


def served(person: Person, unpublished: frozenset[str]) -> str | None:
    roster = with_published_images(Roster(people=(person,)), _BUCKET, _HOST, unpublished)
    return roster.people[0].cdn_image


def test_a_photo_under_review_keeps_its_artifacts_url():
    ken = Person(id="ken", cdn_image=KEN_PHOTO)
    assert served(ken, frozenset({KEN_PHOTO})) == KEN_PHOTO


def test_a_published_photo_is_served_from_the_cdn():
    emma = Person(id="emma", cdn_image=EMMA_PHOTO)
    assert served(emma, frozenset({KEN_PHOTO})) == (
        f"{_HOST}/open-data/vt/local/place_burlington/images/bb48ae910586.png"
    )


def test_unpublished_images_are_the_photos_of_the_changeset_under_review():
    facts = Facts(
        records=(
            record("ken", UNDER_REVIEW, KEN_PHOTO),
            record("darrell", UNDER_REVIEW, None),
            record("emma", PUBLISHED, EMMA_PHOTO),
        )
    )
    assert unpublished_images(facts, UNDER_REVIEW) == frozenset({KEN_PHOTO})


def test_a_published_only_read_has_no_unpublished_images():
    facts = Facts(records=(record("emma", PUBLISHED, EMMA_PHOTO),))
    assert unpublished_images(facts, None) == frozenset()
