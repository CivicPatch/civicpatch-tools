import pytest
from pydantic import BaseModel, ValidationError

from schemas.common import Username


class _Holder(BaseModel):
    username: Username


@pytest.mark.unit
@pytest.mark.parametrize(
    "value,expected",
    [
        ("apple-witch", "apple-witch"),
        ("  apple-witch  ", "apple-witch"),
        ("apple_witch.9", "apple_witch.9"),
        ("x" * 50, "x" * 50),
    ],
)
def test_accepts_and_normalizes_legal_usernames(value, expected):
    assert _Holder(username=value).username == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "apple witch",
        "x" * 51,
        "apple/witch",
        "apple@witch",
    ],
)
def test_rejects_illegal_usernames(value):
    with pytest.raises(ValidationError):
        _Holder(username=value)
