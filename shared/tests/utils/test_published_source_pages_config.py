import pytest

from shared.schemas import PublishedSourcePage, PipelineRunConfig

pytestmark = pytest.mark.unit


def test_known_pages_reach_the_run_but_not_its_saved_context():
    page = PublishedSourcePage(source_url="https://x.gov/", read_source_page_id="r", page_hash="p")
    config = PipelineRunConfig(url="https://x.gov", published_source_pages=[page])

    assert config.published_source_pages == [page]
    assert "published_source_pages" not in config.model_dump()
