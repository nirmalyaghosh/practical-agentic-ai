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
    Decorator to enforce minimum interval between API calls.

    Args:
        min_interval: Minimum seconds between calls (default: 0.02 = 20ms)

    Returns:
        Decorated function with rate limiting applied
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        last_call: list[float] = [0.0]  # Mutable to store state across calls

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            elapsed = time.time() - last_call[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)

            result = func(*args, **kwargs)
            last_call[0] = time.time()
            return result

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
