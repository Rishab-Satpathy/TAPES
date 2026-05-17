"""MCP Permissions for AITAPES v8.0.

Permission boundary enforcement for MCP tool execution.
Authority levels: SAFE < DEV < FULL.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class Authority(StrEnum):
    """Authority levels for MCP operations."""
    SAFE = "safe"   # Read-only
    DEV = "dev"     # Local writes, shell
    FULL = "full"   # Deploy, infra


AUTHORITY_RANK = {Authority.SAFE: 0, Authority.DEV: 1, Authority.FULL: 2}


@dataclass
class PermissionBoundary:
    """Permission boundary for a session or context."""
    authority: Authority
    allowed_tools: list[str] = field(default_factory=list)
    denied_tools: list[str] = field(default_factory=list)
    max_retries: int = 3
    _execution_log: list[dict[str, Any]] = field(default_factory=list)
    _log_lock: threading.Lock = field(default_factory=threading.Lock)
    _MAX_LOG = 10000

    def can_execute(self, tool_name: str) -> bool:
        """Check if a tool is permitted by this boundary."""
        if tool_name in self.denied_tools:
            return False
        if self.allowed_tools and tool_name not in self.allowed_tools:
            return False
        return True

    def check_authority(self, required: Authority) -> bool:
        """Check if this boundary meets the required authority level."""
        return AUTHORITY_RANK.get(self.authority, 0) >= AUTHORITY_RANK.get(required, 0)

    def log_execution(self, tool_name: str, success: bool, error: str | None = None) -> None:
        """Log a tool execution attempt."""
        with self._log_lock:
            if len(self._execution_log) >= self._MAX_LOG:
                self._execution_log.clear()
            self._execution_log.append({
                "tool": tool_name,
                "success": success,
                "error": error,
                "timestamp": datetime.now(UTC).isoformat(),
                "authority": self.authority.value,
            })

    def get_log(self) -> list[dict[str, Any]]:
        """Get the execution log."""
        with self._log_lock:
            return list(self._execution_log)


class Permissions:
    """Permissions manager with authority-based tool access."""

    def __init__(self) -> None:
        self._boundaries: dict[str, PermissionBoundary] = {}
        self._lock = threading.Lock()

    def create_boundary(self, context_id: str, authority: Authority) -> PermissionBoundary:
        """Create a new permission boundary for a context."""
        boundary = PermissionBoundary(authority=authority)
        with self._lock:
            self._boundaries[context_id] = boundary
        logger.info("Created permission boundary for %s with %s authority", context_id, authority.value)
        return boundary

    def get_boundary(self, context_id: str) -> PermissionBoundary | None:
        """Get a permission boundary by context ID."""
        with self._lock:
            return self._boundaries.get(context_id)

    def authorize(self, context_id: str, tool_name: str, required_authority: Authority) -> bool:
        """Authorize a tool execution within a context."""
        boundary = self.get_boundary(context_id)
        if not boundary:
            logger.warning("No permission boundary found for context %s", context_id)
            return False

        if not boundary.check_authority(required_authority):
            logger.warning(
                "Insufficient authority for %s: has %s, needs %s",
                tool_name, boundary.authority.value, required_authority.value
            )
            return False

        if not boundary.can_execute(tool_name):
            logger.warning("Tool %s denied for context %s", tool_name, context_id)
            return False

        return True


_permissions = Permissions()


def get_permissions() -> Permissions:
    """Get the global permissions manager."""
    return _permissions