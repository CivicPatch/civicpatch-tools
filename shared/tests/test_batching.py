import asyncio

import pytest

from shared.utils.batching import gather_in_batches


@pytest.mark.unit
@pytest.mark.asyncio
async def test_answers_in_the_order_given():
    async def double(n: int) -> int:
        await asyncio.sleep(0)
        return n * 2

    assert await gather_in_batches([1, 2, 3, 4, 5], 2, double) == [2, 4, 6, 8, 10]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_never_runs_more_than_the_batch_size_at_once():
    running = 0
    high_water = 0

    async def work(n: int) -> int:
        nonlocal running, high_water
        running += 1
        high_water = max(high_water, running)
        await asyncio.sleep(0)
        running -= 1
        return n

    await gather_in_batches(list(range(10)), 3, work)
    assert high_water == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_an_empty_list_does_no_work():
    async def explode(_: int) -> int:
        raise AssertionError("should not be called")

    assert await gather_in_batches([], 4, explode) == []
