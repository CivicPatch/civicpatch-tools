import pytest

from shared.utils.content_hash import content_hash, hash_texts

pytestmark = pytest.mark.unit


def test_the_same_text_hashes_the_same():
    assert content_hash("# City Council") == content_hash("# City Council")


def test_any_change_moves_the_hash():
    assert content_hash("# City Council") != content_hash("# City Council ")


def test_where_one_text_ends_and_the_next_begins_matters():
    assert hash_texts(["ab", "c"]) != hash_texts(["a", "bc"])


def test_order_matters():
    assert hash_texts(["a", "b"]) != hash_texts(["b", "a"])
