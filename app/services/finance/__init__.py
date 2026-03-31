"""
IFRS Accounting Services.

This package contains service implementations for the IFRS accounting system.
"""

from typing import Any

__all__ = ["platform", "gl", "ap", "ar", "lease", "tax", "cons", "rpt"]


def __getattr__(name: str) -> Any:  # pragma: no cover
    """Lazy import subpackages to avoid importing everything at package import time."""
    if name in __all__:
        module = __import__(f"{__name__}.{name}", fromlist=[name])
        return module
    raise AttributeError(name)
