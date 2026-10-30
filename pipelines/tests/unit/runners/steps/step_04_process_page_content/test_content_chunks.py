"""A page split into pieces that fit the model's input limit."""

import pytest

from runners.pipeline03_people_collector.schemas import RelevantPageResponseSchema
from runners.pipeline03_people_collector.steps.step_04_process_page_content.content_chunks import (
    merged_relevance,
    split_into_chunks,
)

pytestmark = pytest.mark.unit


def test_split_into_chunks_no_split_when_fits():
    content = "## Section\n\nSome content here."
    chunks = split_into_chunks(content, max_chars=10_000)
    assert chunks == [content]


def test_split_into_chunks_splits_large_content():
    # Each section is ~300 chars; max_chars = 2000 keeps the overlap (500) well within capacity
    section = (
        "## Councilmember Jane Smith\n\n"
        + "Contact: 555-1234, jane@city.gov. " * 8
        + "\n\n"
    )
    content = section * 20  # ~6000 chars total
    max_chars = 2_000
    chunks = split_into_chunks(content, max_chars=max_chars)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= max_chars + 500  # tolerance for overlap


def test_split_into_chunks_overlap_carries_context():
    # Each section is ~300 chars; max_chars fits ~3 sections, overlap carries context across boundaries
    sections = [
        f"## Member {i}\n\n" + f"Email: member{i}@city.gov. " * 10 + "\n\n"
        for i in range(10)
    ]
    content = "".join(sections)
    max_chars = 2_000
    chunks = split_into_chunks(content, max_chars=max_chars)
    assert len(chunks) > 1
    # The tail of chunk 0 should appear somewhere in chunk 1 (overlap)
    assert chunks[0][-100:].strip() in chunks[1]


def test_a_page_is_relevant_if_any_piece_is_and_keeps_every_pieces_links_once():
    merged = merged_relevance(
        [
            RelevantPageResponseSchema(is_relevant=False, relevant_urls=["https://town.gov/a", "https://town.gov/b"]),
            RelevantPageResponseSchema(is_relevant=True, relevant_urls=["https://town.gov/b", "https://town.gov/c"]),
        ]
    )

    assert merged == RelevantPageResponseSchema(
        is_relevant=True, relevant_urls=["https://town.gov/a", "https://town.gov/b", "https://town.gov/c"]
    )


def test_a_page_no_piece_finds_relevant_is_not():
    merged = merged_relevance([RelevantPageResponseSchema(is_relevant=False), RelevantPageResponseSchema(is_relevant=False)])

    assert merged.is_relevant is False
