import time
import random
import asyncio
import inspect

BASE_SLEEP = 2

async def with_retry(logger, max_retries, func, *args, **kwargs):
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
                return await result
            else:
                return result
        except Exception as e:
            if retry_attempts < max_retries:
                sleep_time = BASE_SLEEP ** retry_attempts + random.uniform(0, 1)
                logger.warning(f"{e} - Retrying in {sleep_time:.2f} seconds... (Attempt #{retry_attempts + 1})")
                await asyncio.sleep(sleep_time)
                retry_attempts += 1
            else:
                raise e