"""The logging a pure function in `shared` is allowed to do.

`shared` cannot import the pipeline's `PipelineRunLogger` — the dependency only runs the other
way — and cp.org passes a stdlib `Logger`. A `Protocol` is what lets both satisfy the same
parameter without either package knowing about the other.

Its own module because the functions needing it are siblings: neither `merge_utils` nor
`reconcile` imports the other, so defining it in one would couple them for a type alone.
"""

from typing import Protocol


class Log(Protocol):
    # Positional-only: stdlib's `Logger` names the argument `msg`, and a Protocol's named
    # parameters have to match for a class to satisfy it.
    def debug(self, message: str, /) -> None: ...
    def info(self, message: str, /) -> None: ...
    def warning(self, message: str, /) -> None: ...
