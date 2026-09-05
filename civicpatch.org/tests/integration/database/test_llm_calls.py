"""What a run's LLM calls cost, written from the artifact it submitted.

Real Postgres: the insert is a runtime-composed column list against a table with NOT NULL
columns and an FK to `pipeline_runs` — none of which a unit test would catch. It did not catch
the composition being a plain `str`, either.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import pytest
import pytest_asyncio

from database.database import get_pool
from database.llm_calls import record_calls
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_llm_calls/government"


def _call(**overrides) -> dict:
    return {
        "prompt_name": "municipality_officials",
        "source_url": "https://example.gov/council",
        "chunk_index": 1,
        "chunk_count": 2,
        "attempt": 1,
        "seed": None,
        "gateway": "openrouter",
        "model": "deepseek/deepseek-v4-flash",
        "routed_model": "deepseek/deepseek-v4-flash-20260801",
        "upstream_provider": "AtlasCloud",
        "generation_id": "gen-abc",
        "input_tokens": 5260,
        "output_tokens": 2485,
        "cached_input_tokens": 0,
        "reasoning_tokens": 0,
        "cost_usd": "0.001432",
        "web_search": False,
        "duration_ms": 24_000,
        "finish_reason": "stop",
        "error": None,
        **overrides,
    }


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await conn.commit()


async def _rows(run_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT prompt_name, cost_usd, error, finish_reason, chunk_index, attempt "
            "FROM llm_calls WHERE pipeline_run_id = %s ORDER BY created_at",
            (run_id,),
        )
        return await cur.fetchall()


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await _wipe()
    await factories.seed_jurisdiction(_OCDID, "zz")
    yield
    await _wipe()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_run_s_calls_are_written():
    run_id = await factories.start_run(_OCDID)

    # Distinct generation ids: two chunks of one page are two OpenRouter generations, and
    # `llm_calls_generation_uq` would take the second for a resubmission of the first.
    calls = [_call(), _call(chunk_index=2, generation_id="gen-def")]
    assert await record_calls(run_id, calls) == 2
    assert [row[4] for row in await _rows(run_id)] == [1, 2]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resubmitting_an_artifact_does_not_double_count_spend():
    """Submit is an HTTP endpoint: a scraper that retries after a timeout the server actually
    completed re-sends the same `costs.json`. Before `llm_calls_generation_uq` every call was
    written again, and the rows are identical but for `id`, so nothing downstream could tell."""
    run_id = await factories.start_run(_OCDID)
    calls = [_call(), _call(chunk_index=2, generation_id="gen-def")]
    await record_calls(run_id, calls)

    assert await record_calls(run_id, calls) == 0
    assert len(await _rows(run_id)) == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_call_with_no_generation_id_still_lands():
    """The index is partial. A gateway that states no id has nothing to dedupe on, and those
    rows must record rather than collide with each other."""
    run_id = await factories.start_run(_OCDID)

    written = await record_calls(
        run_id, [_call(generation_id=None), _call(generation_id=None, chunk_index=2)]
    )

    assert written == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_call_with_no_stated_cost_is_not_written():
    """Grounded Google calls state none, and `cost_usd` is NOT NULL — a zero would read as free."""
    run_id = await factories.start_run(_OCDID)

    written = await record_calls(
        run_id, [_call(), _call(gateway="google", cost_usd=None)]
    )

    assert written == 1
    assert [row[0] for row in await _rows(run_id)] == ["municipality_officials"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_billed_call_we_could_not_use_is_still_written():
    run_id = await factories.start_run(_OCDID)

    await record_calls(
        run_id, [_call(error="ValidationError: bad json", finish_reason="length")]
    )

    row = (await _rows(run_id))[0]
    assert (row[2], row[3]) == ("ValidationError: bad json", "length")
    assert row[1] is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nothing_to_record_is_not_an_error():
    run_id = await factories.start_run(_OCDID)
    assert await record_calls(run_id, []) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_artifact_missing_a_column_says_so():
    """`.get()` would insert an explicit NULL and raise NotNullViolation on half these columns
    anyway. Better a KeyError naming the field — the caller records best-effort and logs it."""
    run_id = await factories.start_run(_OCDID)
    sparse = _call()
    del sparse["attempt"]

    with pytest.raises(KeyError, match="attempt"):
        await record_calls(run_id, [sparse])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_calls_go_with_the_run_they_belong_to():
    run_id = await factories.start_run(_OCDID)
    await record_calls(run_id, [_call()])

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM pipeline_runs WHERE id = %s", (run_id,))
        await conn.commit()

    assert await _rows(run_id) == []
