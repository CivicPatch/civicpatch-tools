"""The server's diff against the cases the card's diff also runs
(src/frontend/tests/field-model-contract.test.ts), so the two cannot drift."""

import json
from pathlib import Path

import pytest

from core.field_diff import changed_fields

_CASES = json.loads(
    (
        Path(__file__).parents[3] / "src/frontend/tests/fixtures/person-diff-cases.json"
    ).read_text()
)["cases"]


@pytest.mark.unit
@pytest.mark.parametrize("case", _CASES, ids=[case["name"] for case in _CASES])
def test_the_servers_diff_agrees_with_the_cards(case):
    assert changed_fields(case["published"], case["proposed"]) == case["changed"]
