import random
import asyncio
import inspect
import requests
from typing import TypeVar, Callable, Awaitable, Any, cast

BASE_SLEEP = 2

T = TypeVar('T')

def _retry_after_seconds(e: Exception) -> float | None:
    """Returns the Retry-After value from a 429 HTTPError, or None."""
    if isinstance(e, requests.HTTPError) and e.response is not None and e.response.status_code == 429:
        retry_after = e.response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return float(retry_after)
            except ValueError:
                pass
        return 60.0  # conservative fallback if header is missing
    return None

async def with_retry(logger: Any, max_retries: int, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
    """
    Execute a function with retry logic. Supports both sync and async functions.

    Args:
        max_retries: Maximum number of retry attempts.
        func: Function to execute, passed as a callable.
        *args, **kwargs: Arguments to pass to the function.

    Returns:
        The result of the function if successful.

    Raises:
        The last exception encountered if all retries fail.
    """
    retry_attempts = 0

    while retry_attempts <= max_retries:
        try:
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                return cast(T, await result)
            else:
                return cast(T, result)
        except Exception as e:
            if isinstance(e, requests.HTTPError) and e.response is not None and e.response.status_code == 404:
                raise e
            if retry_attempts < max_retries:
                retry_after = _retry_after_seconds(e)
                if retry_after is not None:
                    sleep_time = retry_after + random.uniform(0, 2)
                    logger.warning(f"Rate limited (429) - Retrying in {sleep_time:.2f}s... (Attempt #{retry_attempts + 1})")
                else:
                    sleep_time = BASE_SLEEP ** retry_attempts + random.uniform(0, 1)
                    logger.warning(f"{e} - Retrying in {sleep_time:.2f} seconds... (Attempt #{retry_attempts + 1})")
                await asyncio.sleep(sleep_time)
                retry_attempts += 1
            else:
                raise e
    raise RuntimeError("unreachable — with_retry always returns or raises")