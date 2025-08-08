import time
import random

BASE_SLEEP = 2

def with_retry(max_retries, func):
    """
    Execute a function with retry logic.

    Args:
        max_retries: Maximum number of retry attempts.
        func: Function to execute, passed as a callable.

    Returns:
        The result of the function if successful.

    Raises:
        The last exception encountered if all retries fail.
    """
    retry_attempts = 0

    while retry_attempts <= max_retries:
        try:
            return func()
        except Exception as e:
            if retry_attempts < max_retries:
                sleep_time = BASE_SLEEP ** retry_attempts + random.uniform(0, 1)
                print(f"{e} - Retrying in {sleep_time:.2f} seconds... (Attempt #{retry_attempts + 1})")
                time.sleep(sleep_time)
                retry_attempts += 1
            else:
                raise e