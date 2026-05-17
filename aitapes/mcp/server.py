"""MCP Server for AITAPES v8.0.

MCP protocol server that enforces sandbox boundaries and routes
tool execution through the permission system.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from .permissions import Authority, get_permissions
from .registry import ToolAuthority, get_registry

logger = logging.getLogger(__name__)


class MCPServer:
    """MCP protocol server with sandbox enforcement."""

    def __init__(self) -> None:
        self._permissions = get_permissions()
        self._registry = get_registry()
        self._sandbox_ready = False
        self._lock = threading.Lock()

    def set_sandbox_ready(self, ready: bool = True) -> None:
        """Mark sandbox as ready for execution (must be called before tool execution)."""
        with self._lock:
            self._sandbox_ready = ready
            logger.debug("MCP sandbox ready: %s", ready)

    def is_sandbox_ready(self) -> bool:
        """Check if sandbox is ready for execution."""
        with self._lock:
            return self._sandbox_ready

    def handle_request(
        self,
        method: str,
        params: dict[str, Any] | None,
        context_id: str,
    ) -> dict[str, Any]:
        """Handle an MCP request."""
        if not self.is_sandbox_ready():
            return {
                "error": {"code": -32000, "message": "Sandbox not ready"},
                "id": params.get("id") if params else None,
            }

        if method == "tools/list":
            return self._list_tools()
        elif method == "tools/execute":
            return self._execute_tool(params, context_id)
        elif method == "tools/capabilities":
            return self._capabilities()
        else:
            return {
                "error": {"code": -32601, "message": f"Unknown method: {method}"},
                "id": params.get("id") if params else None,
            }

    def _list_tools(self) -> dict[str, Any]:
        """List available MCP tools."""
        tools = self._registry.get_by_authority(ToolAuthority.SAFE)
        return {
            "result": {
                "tools": [
                    {"name": t.name, "description": t.description, "authority": t.authority.value}
                    for t in tools
                ]
            }
        }

    def _execute_tool(
        self,
        params: dict[str, Any] | None,
        context_id: str,
    ) -> dict[str, Any]:
        """Execute a tool with permission checking."""
        if not params:
            return {"error": {"code": -32602, "message": "Missing params"}}

        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        if not tool_name:
            return {"error": {"code": -32602, "message": "Missing tool name"}}

        boundary = self._permissions.get_boundary(context_id)
        if not boundary:
            return {"error": {"code": -32001, "message": "No permission boundary for context"}}

        tool = self._registry.get(tool_name)
        if not tool:
            return {"error": {"code": -32002, "message": f"Unknown tool: {tool_name}"}}

        tool_authority = Authority(tool.authority.value)

        if not self._permissions.authorize(context_id, tool_name, tool_authority):
            boundary.log_execution(tool_name, success=False, error="Authorization failed")
            return {"error": {"code": -32003, "message": "Tool not authorized"}}

        if tool.handler is None:
            return {"error": {"code": -32004, "message": f"No handler for tool: {tool_name}"}}

        try:
            result = tool.handler(**tool_args)
            boundary.log_execution(tool_name, success=True)
            return {"result": {"output": result}}
        except Exception as e:
            logger.error("Tool execution failed for %s: %s", tool_name, e)
            boundary.log_execution(tool_name, success=False, error=str(e))
            return {"error": {"code": -32005, "message": f"Execution failed: {e}"}}

    def _capabilities(self) -> dict[str, Any]:
        """Return MCP server capabilities."""
        return {
            "result": {
                "capabilities": {
                    "tools": True,
                    "resources": False,
                    "prompts": False,
                },
                "server_info": {
                    "name": "AITAPES MCP Server",
                    "version": "8.0",
                },
            }
        }


_mcp_server = MCPServer()


def get_mcp_server() -> MCPServer:
    """Get the global MCP server instance."""
    return _mcp_server


def check_and_execute(
    tool_name: str,
    tool_args: dict[str, Any],
    context_id: str,
    effective_timeout: int | None = None,
) -> dict[str, Any]:
    """Check permissions and execute a tool.

    Args:
        tool_name: Name of the tool to execute
        tool_args: Arguments to pass to the tool
        context_id: Context ID for permission boundary
        effective_timeout: Computed timeout in seconds (currently unused per F6)
    """
    server = get_mcp_server()
    server.set_sandbox_ready(True)

    return server.handle_request(
        "tools/execute",
        {"name": tool_name, "arguments": tool_args, "id": id(tool_args)},
        context_id,
    )