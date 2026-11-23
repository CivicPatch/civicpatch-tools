"""What decides a stored result a later run may reuse instead of asking the model again. Each
pipeline says what goes in; the hash is taken one way for all of them."""

import inspect
from types import ModuleType
from typing import List

from pydantic import BaseModel, ConfigDict
from shared.utils.content_hash import hash_texts


class CacheKey(BaseModel):
    model_config = ConfigDict(frozen=True)

    # The texts the model read.
    read: List[str]
    # Every prompt the run may send, rendered; anything that changes daily (a date) pinned, or the key
    # never matches twice.
    prompts: List[str]
    # Anything else that changes the result: what a quote is checked against, counts, size limits.
    settings: List[str] = []
    model: str
    # The source of the code that turns the model's answers into what is stored, so a rules change
    # stops reuse. Empty where that code runs again on every reuse.
    rules: List[str] = []


def cache_key_hash(key: CacheKey) -> str:
    return hash_texts([*key.read, *key.prompts, *key.settings, key.model, *key.rules])


def rules_source(modules: List[ModuleType]) -> List[str]:
    return [inspect.getsource(module) for module in modules]
