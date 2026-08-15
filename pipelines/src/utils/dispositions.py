"""Four-way outcome classification for comparing produced values against expected ones.

Recall alone — matches divided by what was expected — is blind to two things. A value the
producer invented where none was wanted is never counted, and a *person* it invented is
never even visited, because the scoring loop iterates over the expected side. Splitting
every comparison into the standard information-extraction taxonomy makes both visible, and
precision, recall and F1 all fall out of the same four counts.

Mirrors the taxonomy already used by the role-normalization eval.
"""

from enum import Enum
from typing import Callable, Hashable, Iterable

from pydantic import BaseModel


class Disposition(str, Enum):
    correct = "correct"
    false_positive = "false_positive"
    false_negative = "false_negative"
    wrong_match = "wrong_match"


def classify_value(
    actual, expected, equals: Callable[[object, object], bool] | None = None
) -> Disposition | None:
    """None when neither side holds a value: a true negative has no denominator to join."""
    equals = equals or (lambda a, b: a == b)
    if not actual and not expected:
        return None
    if not actual:
        return Disposition.false_negative
    if not expected:
        return Disposition.false_positive
    return Disposition.correct if equals(actual, expected) else Disposition.wrong_match


def classify_membership(
    actual_keys: Iterable[Hashable], expected_keys: Iterable[Hashable]
) -> list[Disposition]:
    """Set membership, so `wrong_match` cannot arise — a key either matches or it does not."""
    actual, expected = set(actual_keys), set(expected_keys)
    return (
        [Disposition.correct] * len(actual & expected)
        + [Disposition.false_negative] * len(expected - actual)
        + [Disposition.false_positive] * len(actual - expected)
    )


class Tally(BaseModel):
    correct: int = 0
    false_positive: int = 0
    false_negative: int = 0
    wrong_match: int = 0

    @property
    def produced(self) -> int:
        return self.correct + self.false_positive + self.wrong_match

    @property
    def wanted(self) -> int:
        return self.correct + self.false_negative + self.wrong_match

    @property
    def precision(self) -> float | None:
        return self.correct / self.produced if self.produced else None

    @property
    def recall(self) -> float | None:
        return self.correct / self.wanted if self.wanted else None

    @property
    def f1(self) -> float | None:
        """Computed as 2·TP / (2·TP + FP + FN), not from precision and recall.

        The two forms agree everywhere except the case that matters most here: producing
        nothing at all. Then precision is undefined, and deriving F1 from it yields None —
        so a provider that extracted zero dates out of twelve would slip through a gate
        instead of scoring the 0.0 it has earned. None is reserved for a field with no
        comparisons whatsoever, which is genuinely unjudgeable.
        """
        true_positives = 2 * self.correct
        denominator = (
            true_positives + self.false_positive + self.false_negative + 2 * self.wrong_match
        )
        if denominator == 0:
            return None
        return true_positives / denominator


def tally(dispositions: Iterable[Disposition | None]) -> Tally:
    counts: dict[str, int] = {d.value: 0 for d in Disposition}
    for disposition in dispositions:
        if disposition is not None:
            counts[disposition.value] += 1
    return Tally(**counts)
