"""The hash of everything a run's answer depends on: two places with the same law and the same
questions share it, so the second can copy the first's answer. Pure: inputs in, hash out."""

from typing import List

import services.open_router.prompts as open_router_prompts
from runners.pipeline02_organizations_collector.role_asks import RoleAsk
from runners.pipeline02_organizations_collector.sections import WHOLE_TEXT_CHARS, GoverningLawPage
from services.open_router.llm import MODELS_BY_TYPE
from shared.schemas import GoverningLawKind
from shared.utils.content_hash import hash_texts


def input_hash(
    law: List[tuple[GoverningLawKind, List[GoverningLawPage]]],
    asks: List[RoleAsk],
    presiding: List[RoleAsk],
    asks_per_question: int,
) -> str:
    """`law` is the pages as `sections.pages_by_kind` groups them. Page ids, when the law was
    collected and the place's name are left out: they differ between towns reading one statute."""
    return hash_texts(
        [
            *[text for kind, pages in law for page in pages for text in (kind.value, page.source_url, page.text)],
            *[
                text
                for ask in asks
                for text in (open_router_prompts.governing_role_question(ask.role_label, ask.organization_name), ask.model_dump_json())
            ],
            *_presiding_texts(presiding),
            open_router_prompts.governing_law_reader_prompt(),
            open_router_prompts.governing_sections_prompt(),
            str(asks_per_question),
            str(WHOLE_TEXT_CHARS),
            MODELS_BY_TYPE["STANDARD"]["model"],
        ]
    )


def _presiding_texts(presiding: List[RoleAsk]) -> List[str]:
    if not presiding:
        return []
    question = open_router_prompts.governing_presiding_question(
        presiding[0].organization_name, [(ask.role_id, ask.names) for ask in presiding]
    )
    return [question, *[ask.model_dump_json() for ask in presiding]]
