import threading
import time

from typing import (
    Any,
    Callable,
    TypeVar,
)
from functools import wraps

from googleapiclient.errors import HttpError

from app_logger import get_logger


logger = get_logger(__name__)
T = TypeVar("T")


def rate_limited(min_interval: float = 0.02) -> Callable[[
        Callable[..., T]],
        Callable[..., T]]:
    """
    Decorator to enforce adaptive rate limiting between API calls.

    Each decorated function maintains its own adaptive state (thread-safe).
    Automatically adjusts interval based on API response patterns.

    Args:
        min_interval: Starting/minimum seconds between calls
        (default: 0.02 = 20ms)

    Returns:
        Decorated function with adaptive rate limiting applied
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Per-decorator instance state (not global)
        state = {
            "current_interval": min_interval,
            "min_interval": min_interval,
            "max_interval": 0.5,
            "increase_factor": 1.5,
            "decrease_factor": 0.95,
            "last_call": 0.0,
        }
        # Thread lock for this specific decorator instance
        lock = threading.RLock()

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            with lock:  # Ensure thread-safe access to state
                # Wait based on current adaptive interval
                elapsed = time.time() - state["last_call"]
                current = state["current_interval"]

                if elapsed < current:
                    wait_time = current - elapsed
                    # Release lock during sleep to allow other threads
                    lock.release()
                    try:
                        time.sleep(wait_time)
                    finally:
                        lock.acquire()

            try:
                result = func(*args, **kwargs)

                # Success: gradually decrease interval
                with lock:
                    s_df = state["decrease_factor"]
                    new_interval = max(
                        state["min_interval"],
                        state["current_interval"] * s_df
                    )
                    state["current_interval"] = new_interval
                    state["last_call"] = time.time()

                return result

            except HttpError as e:
                # Rate limit hit: increase interval
                with lock:
                    if e.resp.status == 429:
                        s_if = state["increase_factor"]
                        new_interval = min(
                            state["max_interval"],
                            state["current_interval"] * s_if
                        )
                        state["current_interval"] = new_interval
                        logger.warning(
                            f"Rate limit hit for {func.__name__}, "
                            f"increasing interval to {new_interval*1000:.1f}ms"
                        )
                    state["last_call"] = time.time()
                raise

        return wrapper

    return decorator


def retry_with_backoff(
    func: Callable[..., T],
    max_attempts: int = 3,
    *args: Any,
    **kwargs: Any
) -> T:
    """
    Helper function used to retry API calls with exponential backoff
    for transient errors.

    Args:
        func: The function to execute (typically an API call)
        max_attempts: Maximum number of retry attempts (default: 3)
        *args: Positional arguments to pass to func
        **kwargs: Keyword arguments to pass to func

    Returns:
        Result from successful function execution

    Raises:
        HttpError: After max retries or for non-retryable errors
        Exception: For unexpected non-HTTP errors
    """
    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except HttpError as e:
            if e.resp.status in [429, 500, 503]:  # Retryable errors
                if attempt < max_attempts - 1:
                    wait_time = (2 ** attempt)  # 1s, 2s, 4s
                    logger.warning(
                        f"API error {e.resp.status}, "
                        f"retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{max_attempts})..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Max retries ({max_attempts}) reached")
                    raise
            else:
                # Non-retryable error (401, 404, etc.)
                logger.error(f"Non-retryable error {e.resp.status}: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            raise

    # Type checker satisfaction (unreachable due to raise in loop)
    raise RuntimeError("Retry loop completed without return or raise")
