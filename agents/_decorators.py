"""
Reusable decorators for agent functions.
Centralizes timeout, retry, and error logging logic.
"""
import asyncio
import logging
import time
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)


class AgentTimeoutError(Exception):
    """Raised when an agent operation exceeds its timeout budget."""
    def __init__(self, func_name: str, timeout: float):
        self.func_name = func_name
        self.timeout = timeout
        super().__init__(f"{func_name} timed out after {timeout}s")


class AgentExecutionError(Exception):
    """Wraps unexpected errors from agent runners with context."""
    def __init__(self, func_name: str, original: Exception):
        self.func_name = func_name
        self.original = original
        super().__init__(f"{func_name} failed: {type(original).__name__}: {original}")


def with_timeout(timeout_secs: float) -> Callable:
    """
    Decorator that enforces a hard timeout on an async function.

    On timeout: raises AgentTimeoutError (callers should catch + show user-friendly msg).
    On other errors: re-raises as AgentExecutionError with context.
    Always logs duration for observability.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_secs,
                )
                duration = time.monotonic() - start
                logger.info(
                    "agent_call_ok",
                    extra={
                        "function": func.__name__,
                        "duration_s": round(duration, 2),
                        "timeout_s": timeout_secs,
                    },
                )
                return result
            except asyncio.TimeoutError:
                duration = time.monotonic() - start
                logger.error(
                    "agent_call_timeout",
                    extra={
                        "function": func.__name__,
                        "duration_s": round(duration, 2),
                        "timeout_s": timeout_secs,
                    },
                )
                raise AgentTimeoutError(func.__name__, timeout_secs)
            except (AgentTimeoutError, AgentExecutionError):
                # Already-wrapped errors from nested calls — bubble up
                raise
            except Exception as e:
                duration = time.monotonic() - start
                logger.error(
                    "agent_call_error",
                    extra={
                        "function": func.__name__,
                        "duration_s": round(duration, 2),
                        "error_type": type(e).__name__,
                        "error_msg": str(e)[:200],
                    },
                    exc_info=True,
                )
                raise AgentExecutionError(func.__name__, e)
        return wrapper
    return decorator
