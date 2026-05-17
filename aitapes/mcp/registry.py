"""MCP Tool Registry for AITAPES v8.0.

Registry of all available MCP tools with handlers, authority levels,
and permission boundaries.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ToolAuthority(StrEnum):
    """Authority level for tool execution."""
    SAFE = "safe"    # Read-only operations
    DEV = "dev"      # Local development (writes, shell)
    FULL = "full"    # Deploy/infra operations


@dataclass
class ToolDefinition:
    """Definition of an MCP tool."""
    name: str
    description: str
    authority: ToolAuthority
    handler: Callable[..., Any] | None = None
    parameters: dict[str, Any] | None = None
    retry_on_failure: bool = False
    timeout_seconds: int = 30


class ToolRegistry:
    """Registry of MCP tools with handlers."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._authority_cache: dict[str, ToolAuthority] = {}
        self._L1_CACHE: dict[str, ToolDefinition] = {}
        self._L1_MAX = 1000

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        self._authority_cache[tool.name] = tool.authority
        logger.debug("Registered MCP tool: %s (%s)", tool.name, tool.authority.value)

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool by name."""
        if name in self._L1_CACHE:
            return self._L1_CACHE[name]
        tool = self._tools.get(name)
        if tool:
            if len(self._L1_CACHE) >= self._L1_MAX:
                self._L1_CACHE.clear()
            self._L1_CACHE[name] = tool
        return tool

    def get_by_authority(self, authority: ToolAuthority) -> list[ToolDefinition]:
        """Get all tools at or below a given authority level."""
        ranks = {"safe": 0, "dev": 1, "full": 2}
        target = ranks.get(authority.value, 0)
        result = []
        for tool in self._tools.values():
            if ranks.get(tool.authority.value, 0) <= target:
                result.append(tool)
        return result

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools


_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _registry


# ── Built-in tool definitions ────────────────────────────────────────────────

_DEV_TOOLS = [
    ToolDefinition(
        name="fs_read",
        description="Read file contents",
        authority=ToolAuthority.SAFE,
        handler=None,  # B12: Will be wired to filesystem adapter
        parameters={"path": {"type": "string", "required": True}},
    ),
    ToolDefinition(
        name="fs_write",
        description="Write content to a file",
        authority=ToolAuthority.DEV,
        handler=None,
        parameters={"path": {"type": "string"}, "content": {"type": "string"}},
    ),
    ToolDefinition(
        name="fs_list",
        description="List directory contents",
        authority=ToolAuthority.SAFE,
        handler=None,
        parameters={"path": {"type": "string", "required": True}},
    ),
    ToolDefinition(
        name="shell_run",
        description="Execute shell command",
        authority=ToolAuthority.DEV,
        handler=None,
        parameters={"command": {"type": "string", "required": True}, "cwd": {"type": "string"}},
        timeout_seconds=60,
    ),
    ToolDefinition(
        name="git_status",
        description="Show git working tree status",
        authority=ToolAuthority.SAFE,
        handler=None,
    ),
]

_FULL_TOOLS = [
    ToolDefinition(
        name="git_branch",
        description="Create a new git branch",
        authority=ToolAuthority.DEV,
        handler=None,
        parameters={"name": {"type": "string", "required": True}},
    ),
    ToolDefinition(
        name="docker_build",
        description="Build a Docker image",
        authority=ToolAuthority.FULL,
        handler=None,
        parameters={"tag": {"type": "string", "required": True}, "path": {"type": "string"}},
        timeout_seconds=300,
    ),
    ToolDefinition(
        name="docker_run",
        description="Run a Docker container",
        authority=ToolAuthority.FULL,
        handler=None,
        parameters={"image": {"type": "string", "required": True}, "command": {"type": "string"}},
        timeout_seconds=120,
    ),
    ToolDefinition(
        name="docker_push",
        description="Push Docker image to registry",
        authority=ToolAuthority.FULL,
        handler=None,
        parameters={"tag": {"type": "string", "required": True}},
        timeout_seconds=180,
    ),
]


def register_builtin_tools() -> None:
    """Register all built-in MCP tools."""
    for tool in _DEV_TOOLS:
        _registry.register(tool)
    for tool in _FULL_TOOLS:
        _registry.register(tool)
    logger.info("Registered %d MCP tools", len(_registry.list_tools()))


register_builtin_tools()