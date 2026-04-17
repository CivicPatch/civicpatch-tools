import json
import logging
import httpx
import pytest
from runners.people_collector.steps.step_08_format_output.format_output import (
    format_output,
    _maybe_add_fallback_url,
    _get_image_map,
    _swap_local_image,
)
from runners.people_collector.schemas import PipelineStatus, FormatOutputStep, MergeRecordsAcrossLLMsStep
from tests.factories.official import official_factory
from tests.factories.person import person_factory
from tests.factories.pipeline_run_context import pipeline_run_context_factory

pytestmark = pytest.mark.unit

logger = logging.getLogger(__name__)

AUSTIN_OCDID = "ocd-jurisdiction/country:us/state:tx/place:austin/government"


def test__maybe_add_fallback_url():
    person = official_factory(name="John Doe", urls=[], source_urls=["https://example.com/john_doe"])
    updated_person = _maybe_add_fallback_url(person)
    assert updated_person.urls == ["https://example.com/john_doe"]

    person_with_url = official_factory(name="Jane Smith", urls=["https://example.com/jane_smith"], source_urls=["https://example.com/city_council"])
    updated_person_with_url = _maybe_add_fallback_url(person_with_url)
    assert updated_person_with_url.urls == ["https://example.com/jane_smith"]

@pytest.mark.asyncio
async def test_format_output(httpx_mock):
    httpx_mock.add_response(
        status_code=200,
        json={"resolved_people": []}
    )

    people = [
        person_factory(name="John Doe", urls=[], source_urls=["https://example.com/john_doe"]),
        person_factory(name="Jane Smith", urls=[], source_urls=["https://example.com/jane_smith"]),
    ]

    context = pipeline_run_context_factory({
        PipelineStatus.MERGE_RECORDS_ACROSS_LLMS: MergeRecordsAcrossLLMsStep(people=people),
    })

    async with httpx.AsyncClient() as api_client:
        output = await format_output(context, api_client)

    assert isinstance(output, FormatOutputStep)
    assert len(output.officials) == 2
    assert output.officials[0].urls == ["https://example.com/john_doe"]
    assert output.officials[1].urls == ["https://example.com/jane_smith"]


# ── _get_image_map ────────────────────────────────────────────

def test_get_image_map_returns_empty_when_data_source_missing():
    result = _get_image_map("ocd-jurisdiction/country:us/state:xx/place:nowhere/government", logger)
    assert result == {}


def test_get_image_map_returns_empty_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ROOT", str(tmp_path))
    images_dir = tmp_path / "data_source" / "tx" / "local" / "place_austin"
    images_dir.mkdir(parents=True)

    result = _get_image_map(AUSTIN_OCDID, logger)
    assert result == {}


def test_get_image_map_reads_file(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ROOT", str(tmp_path))
    images_dir = tmp_path / "data_source" / "tx" / "local" / "place_austin" / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "image_map.json").write_text(json.dumps({"abc123.png": "https://example.gov/abc123.png"}))

    result = _get_image_map(AUSTIN_OCDID, logger)
    assert result == {"abc123.png": "https://example.gov/abc123.png"}


# ── _swap_local_image ─────────────────────────────────────────

def test_swap_local_image_sets_cdn_image_and_original_url():
    official = official_factory(name="Alice")
    official.image = "local://abc123.png"

    result = _swap_local_image(official, {"abc123.png": "https://example.gov/alice.png"})

    assert result.image == "https://example.gov/alice.png"
    assert result.cdn_image == "local://abc123.png"


def test_swap_local_image_skips_non_local_image():
    official = official_factory(name="Bob")
    official.image = "https://example.gov/bob.png"

    result = _swap_local_image(official, {"bob.png": "https://example.gov/bob.png"})

    assert result.image == "https://example.gov/bob.png"
    assert result.cdn_image is None


def test_swap_local_image_skips_basename_not_in_map():
    official = official_factory(name="Carol")
    official.image = "local://notinmap.png"

    result = _swap_local_image(official, {})

    assert result.image == "local://notinmap.png"
    assert result.cdn_image is None


def test_swap_local_image_skips_no_image():
    official = official_factory(name="Dave")
    official.image = None

    result = _swap_local_image(official, {"x.png": "https://example.gov/x.png"})

    assert result.image is None
    assert result.cdn_image is None
