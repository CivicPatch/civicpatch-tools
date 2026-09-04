import pytest

from core.output_hash import hash_rows, hash_text


@pytest.mark.unit
def test_the_same_rows_hash_the_same():
    rows = [["Jane Doe", "Mayor"], ["Sam Lee", "Council"]]
    assert hash_rows(rows) == hash_rows([["Jane Doe", "Mayor"], ["Sam Lee", "Council"]])


@pytest.mark.unit
def test_order_is_part_of_the_identity():
    """Every query feeding a sink has an ORDER BY, so two orderings are two different writes —
    a reordered tab is a real change to whoever reads it."""
    assert hash_rows([["a"], ["b"]]) != hash_rows([["b"], ["a"]])


@pytest.mark.unit
def test_a_moved_cell_changes_the_hash():
    """The gate exists to catch this: same row count, same values, different placement."""
    assert hash_rows([["a", "b"]]) != hash_rows([["b", "a"]])


@pytest.mark.unit
def test_a_field_boundary_cannot_be_faked():
    """Joining the rows would make these identical, which would let a real edit skip the write."""
    assert hash_rows([["ab", "c"]]) != hash_rows([["a", "bc"]])


@pytest.mark.unit
def test_non_ascii_survives():
    """`ensure_ascii=False`, so an accented name is hashed as itself rather than escaped."""
    assert hash_rows([["Ana Peña"]]) == hash_rows([["Ana Peña"]])
    assert hash_rows([["Ana Peña"]]) != hash_rows([["Ana Pena"]])


@pytest.mark.unit
def test_text_hashing_is_plain_sha256():
    """Git's payload is the YAML string itself, not rows — and the hash is unkeyed, unlike
    `lib.hash.hash_string`, which is HMAC-SHA512 for signing."""
    assert hash_text("") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
