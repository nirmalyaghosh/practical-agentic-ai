import time

from typing import (
    Any,
    Callable,
    TypeVar,
)
from functools import wraps


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
