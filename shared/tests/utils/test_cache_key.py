import pytest

from shared.utils import content_hash
from shared.utils.cache_key import CacheKey, cache_key_hash, rules_source

pytestmark = pytest.mark.unit

_KEY = CacheKey(read=["§ 1. The council"], prompts=["Who sits on the council?"], model="deepseek/deepseek-v4-flash")


def test_the_same_key_hashes_the_same():
    assert cache_key_hash(_KEY) == cache_key_hash(_KEY.model_copy())


@pytest.mark.parametrize(
    "change",
    [
        {"read": ["§ 1. The board"]},
        {"prompts": ["Who chairs the council?"]},
        {"settings": ["2"]},
        {"model": "another/model"},
        {"rules": ["def verify(): ..."]},
    ],
)
def test_any_part_moves_the_hash(change: dict):
    assert cache_key_hash(_KEY.model_copy(update=change)) != cache_key_hash(_KEY)


def test_rules_are_the_modules_source():
    [source] = rules_source([content_hash])

    assert "def hash_texts(" in source
