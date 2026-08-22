import json
import os
from unittest.mock import MagicMock

import pytest
from runners.people_collector.steps.step_05_cleanup.cleanup import (
    cleanup_cache,
    cleanup_images,
)
from shared.schemas import PersonRecord
from shared.utils import url_utils

pytestmark = pytest.mark.unit


def _record(label="Mayor", image=None, source_url="https://zz.gov/council", url=None):
    return PersonRecord(
        name="Ann Lee", label=label, image=image, source_url=source_url, url=url
    )


def _images(tmp_path, files: dict, image_map: dict):
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    for name, body in files.items():
        (images_dir / name).write_text(body)
    (images_dir / "image_map.json").write_text(json.dumps(image_map))
    return str(images_dir)


def test_an_image_no_record_points_at_is_removed(tmp_path):
    images_dir = _images(
        tmp_path,
        {"kept.png": "x", "orphan.png": "x"},
        {"kept.png": "https://zz.gov/ann.png", "orphan.png": "https://zz.gov/old.png"},
    )

    cleanup_images(MagicMock(), images_dir, [_record(image="local://kept.png")])

    assert sorted(os.listdir(images_dir)) == ["image_map.json", "kept.png"]


def test_the_map_loses_the_entries_whose_files_went(tmp_path):
    """cp.org reads this map to resolve provenance, so an entry naming a deleted file is a
    dead lookup."""
    images_dir = _images(
        tmp_path,
        {"kept.png": "x", "orphan.png": "x"},
        {"kept.png": "https://zz.gov/ann.png", "orphan.png": "https://zz.gov/old.png"},
    )

    cleanup_images(MagicMock(), images_dir, [_record(image="local://kept.png")])

    with open(os.path.join(images_dir, "image_map.json")) as f:
        assert json.load(f) == {"kept.png": "https://zz.gov/ann.png"}


def test_a_record_naming_a_missing_image_is_reported(tmp_path):
    images_dir = _images(tmp_path, {}, {})
    logger = MagicMock()

    cleanup_images(logger, images_dir, [_record(image="local://gone.png")])

    assert logger.error.called


def test_a_record_with_no_image_keeps_nothing(tmp_path):
    images_dir = _images(tmp_path, {"orphan.png": "x"}, {"orphan.png": "https://zz.gov/x"})

    cleanup_images(MagicMock(), images_dir, [_record()])

    assert os.listdir(images_dir) == ["image_map.json"]


def test_a_cached_page_no_record_came_from_is_removed(tmp_path):
    """Folder names are the url run through `format_url_to_folder`, which is how a record's
    `source_url` finds the page it was read from."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    kept = url_utils.format_url_to_folder("https://zz.gov/council")
    (cache_dir / kept).mkdir()
    (cache_dir / "some-other-page").mkdir()

    cleanup_cache(str(cache_dir), [_record(source_url="https://zz.gov/council")])

    assert os.listdir(str(cache_dir)) == [kept]


def test_a_page_only_reached_as_a_persons_url_is_kept(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    bio = url_utils.format_url_to_folder("https://zz.gov/ann")
    (cache_dir / bio).mkdir()

    cleanup_cache(str(cache_dir), [_record(url="https://zz.gov/ann")])

    assert os.listdir(str(cache_dir)) == [bio]
