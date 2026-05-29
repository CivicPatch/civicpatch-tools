import random
from pathlib import Path

import yaml

_WORDLISTS_PATH = Path(__file__).parent / "usernames.yml"


def _load_wordlists() -> tuple[list[str], list[str], list[str]]:
    with _WORDLISTS_PATH.open() as f:
        data = yaml.safe_load(f)
    return data["adjectives"], data["nouns"], data["places"]


_ADJECTIVES, _NOUNS, _PLACES = _load_wordlists()


def pick_two_words() -> str:
    return f"{random.choice(_ADJECTIVES)}-{random.choice(_NOUNS)}"


def append_place(name: str) -> str:
    return f"{name}-{random.choice(_PLACES)}"


def append_numeric_suffix(name: str) -> str:
    return f"{name}-{random.randint(1000, 9999)}"
