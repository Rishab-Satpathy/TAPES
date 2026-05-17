"""Observability Module for TAPES v8.0.

Cherry-picked from NovelIdeaEdition's runtime_observer.py.
Provides ComplexityTracker, TAPESLogger, and setup_logging.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ComplexityTracker:
    """Tracks patch complexity for refresh decisions."""
    patch_complexity: int = 0
    refresh_count: int = 0
    _applied_patches: list[dict[str, Any]] = field(default_factory=list)

    def add_patch(self, patch_info: dict[str, Any] | None = None) -> None:
        """Record a patch and increment complexity counter."""
        self.patch_complexity += 1
        self._applied_patches.append(patch_info or {})

    def should_refresh(self, threshold: int = 50) -> bool:
        """Check if complexity threshold triggers refresh."""
        return self.patch_complexity >= threshold

    def reset(self) -> None:
        """Reset complexity counter after refresh."""
        self.patch_complexity = 0
        self.refresh_count += 1

    def summary(self) -> dict[str, Any]:
        return {
            "patch_complexity": self.patch_complexity,
            "refresh_count": self.refresh_count,
            "patches_tracked": len(self._applied_patches),
        }


class TAPESLogger:
    """Structured logger for TAPES operations."""

    def __init__(self, name: str = "tapes", level: int = logging.INFO) -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)

    def info(self, message: str, **kwargs: Any) -> None:
        self._logger.info(message, extra=kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._logger.warning(message, extra=kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._logger.error(message, extra=kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._logger.debug(message, extra=kwargs)


def setup_logging(level: str = "INFO", log_file: str | None = None) -> None:
    """Configure logging for TAPES."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )