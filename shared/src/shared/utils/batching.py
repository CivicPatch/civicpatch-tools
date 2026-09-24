"""Running async work a few at a time."""

import asyncio
from collections.abc import Awaitable, Callable


async def gather_in_batches[T, R](
    items: list[T], size: int, work: Callable[[T], Awaitable[R]]
) -> list[R]:
    """`work` applied to every item, `size` at a time, answers in the order given.

    Not one `asyncio.gather` over all of them: a unit of work may hold a database connection
    for its whole life, so an unbounded fan-out over a long list asks for more connections than
    the pool has and every one of them waits out the timeout instead.
    """
    results: list[R] = []
    for start in range(0, len(items), size):
        batch = items[start : start + size]
        results.extend(await asyncio.gather(*[work(item) for item in batch]))
    return results
