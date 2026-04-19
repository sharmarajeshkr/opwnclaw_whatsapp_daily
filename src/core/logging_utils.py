import time
import functools
import asyncio
import logging
from typing import Any, Callable

class ContextAdapter(logging.LoggerAdapter):
    """
    Standardizes log context.
    Usage:
        logger = ContextAdapter(get_logger("MyModule"), {"phone": "919..."})
        logger.info("Message") # Will include 'phone' in the extra field
    """
    def process(self, msg, kwargs):
        kwargs.setdefault("extra", {}).update(self.extra)
        # Prepend context to the message for the console handler string
        context_str = f"[{self.extra.get('phone', 'Global')}] "
        return f"{context_str}{msg}", kwargs

def log_duration(logger: logging.Logger):
    """
    Decorator to log the execution time of an async or sync function.
    """
    def decorator(func: Callable):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.perf_counter() - start
                    logger.debug(f"⏱️ {func.__name__} took {duration:.4f}s")
                    return result
                except Exception:
                    duration = time.perf_counter() - start
                    logger.error(f"❌ {func.__name__} failed after {duration:.4f}s")
                    raise
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    duration = time.perf_counter() - start
                    logger.debug(f"⏱️ {func.__name__} took {duration:.4f}s")
                    return result
                except Exception:
                    duration = time.perf_counter() - start
                    logger.error(f"❌ {func.__name__} failed after {duration:.4f}s")
                    raise
            return sync_wrapper
    return decorator
