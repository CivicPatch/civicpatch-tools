"""A page split into pieces that each fit under the model's input limit, for every step 4 call
that sends a page's content, and the pieces' relevance answers made one."""

from typing import List

import services.open_router.llm as open_router_llm
from runners.pipeline03_people_collector.constants import CHUNK_OVERLAP_CHARS
from runners.pipeline03_people_collector.schemas import RelevantPageResponseSchema
from semantic_text_splitter import MarkdownSplitter


def content_chunks(content: str, prompt: str) -> list[str]:
    return split_into_chunks(content, open_router_llm.max_content_chars(prompt))


def split_into_chunks(content: str, max_chars: int) -> list[str]:
    if len(content) <= max_chars:
        return [content]
    return MarkdownSplitter(max_chars, overlap=CHUNK_OVERLAP_CHARS).chunks(content)


def merged_relevance(answers: List[RelevantPageResponseSchema]) -> RelevantPageResponseSchema:
    """Relevant if any piece is; every piece's links, in order, each once."""
    return RelevantPageResponseSchema(
        is_relevant=any(answer.is_relevant for answer in answers),
        relevant_urls=list(dict.fromkeys(url for answer in answers for url in answer.relevant_urls)),
    )
