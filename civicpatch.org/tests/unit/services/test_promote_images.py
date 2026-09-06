"""Promoting a roster's photos at publish.

The copies are the reason this is worth a test of its own: they are the only network I/O on
the publish request, one blocking round trip per photo, and they used to run in series.
"""

import asyncio
from unittest.mock import patch

import pytest

from services.publish import promote_images

pytestmark = pytest.mark.unit

ARTIFACT = "https://storage.example/civicpatch-artifacts/run-1/data_source/images/abc123.png"


def _person(name: str, image: str | None = ARTIFACT) -> dict:
    return {"id": name.lower(), "name": name, "cdn_image": image}


@pytest.fixture(autouse=True)
def _env():
    with patch(
        "environment.get_env_vars",
        return_value={"FRIENDLY_STORAGE_HOST": "cdn.civicpatch.org"},
    ):
        yield


@pytest.mark.asyncio
async def test_the_roster_comes_back_in_the_order_it_went_in():
    """`gather` preserves order, and the caller hands the result straight to the publish."""
    people = [_person("Ann Lee"), _person("Bo Ray"), _person("Cy Fox")]

    with patch("lib.storage.copy_object"):
        promoted = await promote_images(people)

    assert [person["name"] for person in promoted] == ["Ann Lee", "Bo Ray", "Cy Fox"]


@pytest.mark.asyncio
async def test_the_copies_overlap_rather_than_queueing_behind_each_other():
    """The point of the change. Nine councillors were nine serial round trips inside the
    publish request; sleeping in the fake makes serial execution measurable."""
    people = [_person(f"Person {n}") for n in range(6)]
    import time

    def slow_copy(*_args, **_kwargs):
        time.sleep(0.05)

    with patch("lib.storage.copy_object", side_effect=slow_copy):
        started = time.perf_counter()
        await promote_images(people)
        elapsed = time.perf_counter() - started

    # Six × 50ms is 300ms in series. Generous bound: this asserts "overlapped", not a duration.
    assert elapsed < 0.2


@pytest.mark.asyncio
async def test_a_photo_that_will_not_copy_leaves_that_person_alone():
    """Best-effort by design: the record keeps pointing at the artifacts bucket, where the URL
    still resolves, rather than failing a publish whose roster is otherwise fine."""
    people = [_person("Ann Lee"), _person("Bo Ray")]

    def fail_for_one(_src_bucket, source_key, *_rest, **_kw):
        raise RuntimeError("no such key")

    with patch("lib.storage.copy_object", side_effect=fail_for_one):
        promoted = await promote_images(people)

    assert [person["cdn_image"] for person in promoted] == [ARTIFACT, ARTIFACT]


@pytest.mark.asyncio
async def test_somebody_with_no_photo_is_passed_through_untouched():
    with patch("lib.storage.copy_object") as copy:
        promoted = await promote_images([_person("Ann Lee", image=None)])

    copy.assert_not_called()
    assert promoted[0]["cdn_image"] is None
