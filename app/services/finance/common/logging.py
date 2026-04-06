"""
Logging Utilities - Structured logging for IFRS services.

Provides consistent, contextual logging across all IFRS modules
with support for performance monitoring and correlation tracking.
"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any, TypeVar
from uuid import UUID

logger = logging.getLogger(__name__)

# Context variables for request-scoped logging context
_log_context_org_id: ContextVar[str | None] = ContextVar("log_org_id", default=None)
_log_context_user_id: ContextVar[str | None] = ContextVar("log_user_id", default=None)
_log_context_correlation_id: ContextVar[str | None] = ContextVar(
    "log_correlation_id", default=None
)


def set_log_context(
    organization_id: UUID | str | None = None,
    user_id: UUID | str | None = None,
    correlation_id: str | None = None,
) -> None:
    """
    Set logging context for the current request.

    Args:
        organization_id: Current organization ID
        user_id: Current user ID
        correlation_id: Request correlation ID
    """
    if organization_id:
        _log_context_org_id.set(str(organization_id))
    if user_id:
        _log_context_user_id.set(str(user_id))
    if correlation_id:
        _log_context_correlation_id.set(correlation_id)


def clear_log_context() -> None:
    """Clear logging context."""
    _log_context_org_id.set(None)
    _log_context_user_id.set(None)
    _log_context_correlation_id.set(None)


def get_log_context() -> dict[str, str | None]:
    """Get current logging context."""
    return {
        "org_id": _log_context_org_id.get(),
        "user_id": _log_context_user_id.get(),
        "correlation_id": _log_context_correlation_id.get(),
    }


class ContextualLogger:
    """Logger wrapper that passes context as structured ``extra`` fields.

    ``JsonLogFormatter`` picks up ``org_id``, ``correlation_id``, etc. from
    the ``extra`` dict and emits them as top-level JSON keys.  This makes
    context **filterable** in Loki (``| json | org_id="abc123"``) rather
    than requiring regex on a concatenated message string.

    Usage::

        logger = ContextualLogger(__name__)
        logger.info("Processing invoice", invoice_id=invoice_id)

    Output (via JsonLogFormatter)::

        {"message": "Processing invoice", "org_id": "abc123...", "invoice_id": "789", ...}
    """

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)
        self._name = name

    def _extra(self, **kwargs: Any) -> dict[str, Any]:
        """Build an ``extra`` dict merging log context vars with caller kwargs."""
        context = get_log_context()
        extra: dict[str, Any] = {}
        for key in ("org_id", "user_id", "correlation_id"):
            val = context.get(key)
            if val:
                extra[key] = val
        extra.update(kwargs)
        return extra

    def debug(self, message: str, **kwargs: Any) -> None:
        self._logger.debug(message, extra=self._extra(**kwargs))

    def info(self, message: str, **kwargs: Any) -> None:
        self._logger.info(message, extra=self._extra(**kwargs))

    def warning(self, message: str, **kwargs: Any) -> None:
        self._logger.warning(message, extra=self._extra(**kwargs))

    def error(self, message: str, **kwargs: Any) -> None:
        self._logger.error(message, extra=self._extra(**kwargs))

    def exception(self, message: str, **kwargs: Any) -> None:
        self._logger.exception(message, extra=self._extra(**kwargs))


def get_logger(name: str) -> ContextualLogger:
    """
    Get a contextual logger for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        ContextualLogger instance
    """
    return ContextualLogger(name)


# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


def log_slow_operation(
    threshold_ms: int = 500,
    logger: logging.Logger | None = None,
) -> Callable[[F], F]:
    """Decorator to log slow operations.

    Args:
        threshold_ms: Log warning if operation takes longer than this (milliseconds)
        logger: Logger to use (defaults to module logger)

    Usage::

        @log_slow_operation(threshold_ms=500)
        def expensive_query(...):
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                if elapsed_ms > threshold_ms:
                    log = logger or logging.getLogger(func.__module__)
                    context = get_log_context()
                    log.warning(
                        "Slow operation: %s.%s took %.1fms (threshold: %dms)",
                        func.__module__,
                        func.__name__,
                        elapsed_ms,
                        threshold_ms,
                        extra={k: v for k, v in context.items() if v is not None},
                    )

        return wrapper  # type: ignore

    return decorator


def log_service_call(
    logger: logging.Logger | None = None,
    log_args: bool = False,
    log_result: bool = False,
) -> Callable[[F], F]:
    """
    Decorator to log service method calls.

    Args:
        logger: Logger to use (defaults to module logger)
        log_args: Log method arguments
        log_result: Log method result

    Usage:
        @log_service_call()
        def create_invoice(...):
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            log = logger or logging.getLogger(func.__module__)
            ctx_extra = {k: v for k, v in get_log_context().items() if v is not None}

            if log_args:
                log.debug(
                    "Calling %s args=%r kwargs=%r",
                    func.__name__,
                    args[1:],
                    kwargs,
                    extra=ctx_extra,
                )
            else:
                log.debug("Calling %s", func.__name__, extra=ctx_extra)

            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                if log_result:
                    log.debug(
                        "%s completed in %.1fms result=%r",
                        func.__name__,
                        elapsed_ms,
                        result,
                        extra=ctx_extra,
                    )
                else:
                    log.debug(
                        "%s completed in %.1fms",
                        func.__name__,
                        elapsed_ms,
                        extra=ctx_extra,
                    )
                return result

            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                log.exception(
                    "%s failed after %.1fms: %s",
                    func.__name__,
                    elapsed_ms,
                    e,
                    extra=ctx_extra,
                )
                raise

        return wrapper  # type: ignore

    return decorator


def log_db_error(
    logger: logging.Logger | None = None,
    operation: str = "database operation",
) -> Callable[[F], F]:
    """Decorator to log database errors with context.

    Args:
        logger: Logger to use
        operation: Description of the operation

    Usage::

        @log_db_error(operation="create invoice")
        def create_invoice(...):
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log = logger or logging.getLogger(func.__module__)
                ctx_extra = {
                    k: v for k, v in get_log_context().items() if v is not None
                }
                log.exception(
                    "Database error in %s: %s",
                    operation,
                    e,
                    extra=ctx_extra,
                )
                raise

        return wrapper  # type: ignore

    return decorator


class ServiceLogger:
    """
    Mixin class to add logging capabilities to services.

    Usage:
        class MyService(ServiceLogger):
            def create_item(self):
                self.log_info("Creating item", item_id=123)
    """

    @property
    def _service_logger(self) -> ContextualLogger:
        """Get logger for this service class."""
        if not hasattr(self, "_logger_instance"):
            self._logger_instance = get_logger(self.__class__.__module__)
        return self._logger_instance

    def log_debug(self, message: str, **kwargs: Any) -> None:
        self._service_logger.debug(message, **kwargs)

    def log_info(self, message: str, **kwargs: Any) -> None:
        self._service_logger.info(message, **kwargs)

    def log_warning(self, message: str, **kwargs: Any) -> None:
        self._service_logger.warning(message, **kwargs)

    def log_error(self, message: str, **kwargs: Any) -> None:
        self._service_logger.error(message, **kwargs)

    def log_exception(self, message: str, **kwargs: Any) -> None:
        self._service_logger.exception(message, **kwargs)
