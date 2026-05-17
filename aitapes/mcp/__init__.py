"""MCP Module for AITAPES v8.0.

MCP (Model Context Protocol) execution layer for tool execution.
Only active during EXECUTE phase, controlled by TAPES kernel.
"""

from __future__ import annotations

from .registry import ToolAuthority, ToolDefinition, ToolRegistry, get_registry
from .permissions import Authority, PermissionBoundary, Permissions, get_permissions
from .server import MCPServer, get_mcp_server, check_and_execute
from .transport import StdioTransport, HTTPTransport, create_transport

__all__ = [
    "ToolAuthority",
    "ToolDefinition",
    "ToolRegistry",
    "get_registry",
    "Authority",
    "PermissionBoundary",
    "Permissions",
    "get_permissions",
    "MCPServer",
    "get_mcp_server",
    "check_and_execute",
    "StdioTransport",
    "HTTPTransport",
    "create_transport",
]