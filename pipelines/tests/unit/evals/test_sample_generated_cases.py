import pytest
from eval_utils import (
    ALL_CASES,
    DEFAULT_SAMPLE_SIZE,
    GENERATED_KEY,
    SAMPLE_SIZE_ENV,
    sample_generated_cases,
    sample_settings,
)

pytestmark = pytest.mark.unit


def _case(case_id: str, generated: bool) -> dict:
    expected = {GENERATED_KEY: True} if generated else {}
    return {"id": case_id, "expected": expected}


WRITTEN = [_case("jackson", False), _case("millbury", False)]
GENERATED = [_case(f"generated_{i}", True) for i in range(10)]


def test_no_sample_size_keeps_every_case():
    assert sample_generated_cases(WRITTEN + GENERATED, None, seed=0) == WRITTEN + GENERATED


def test_hand_written_cases_always_run():
    sampled = sample_generated_cases(WRITTEN + GENERATED, 3, seed=0)

    assert sampled[:2] == WRITTEN
    assert len(sampled) == 5


def test_the_same_seed_picks_the_same_cases():
    first = sample_generated_cases(WRITTEN + GENERATED, 3, seed=7)
    second = sample_generated_cases(list(reversed(WRITTEN + GENERATED)), 3, seed=7)

    assert [c["id"] for c in first[2:]] == [c["id"] for c in second[2:]]


def test_a_sample_bigger_than_the_generated_cases_keeps_them_all():
    assert len(sample_generated_cases(WRITTEN + GENERATED, 50, seed=0)) == 12


def test_unset_sample_size_uses_the_default(monkeypatch):
    monkeypatch.delenv(SAMPLE_SIZE_ENV, raising=False)

    assert sample_settings() == (DEFAULT_SAMPLE_SIZE, 0)


def test_all_runs_every_generated_case(monkeypatch):
    monkeypatch.setenv(SAMPLE_SIZE_ENV, ALL_CASES)

    assert sample_settings()[0] is None
