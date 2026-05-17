"""MCP Transport Layer for AITAPES v8.0.

Supports stdio and HTTP transport modes for MCP protocol.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MCPMessage:
    """MCP protocol message."""
    jsonrpc: str = "2.0"
    method: str = ""
    params: dict[str, Any] | None = None
    id: str | int | None = None


class Transport(ABC):
    """Abstract base class for MCP transport."""

    @abstractmethod
    def send(self, message: MCPMessage) -> None:
        """Send a message."""

    @abstractmethod
    def receive(self) -> MCPMessage | None:
        """Receive a message."""

    @abstractmethod
    def close(self) -> None:
        """Close the transport."""


class StdioTransport(Transport):
    """stdio transport for local execution."""

    def __init__(self) -> None:
        self._closed = False

    def send(self, message: MCPMessage) -> None:
        """Send message to stdout."""
        if self._closed:
            return
        payload = {
            "jsonrpc": message.jsonrpc,
            "method": message.method,
            "params": message.params or {},
            "id": message.id,
        }
        print(json.dumps(payload), flush=True)

    def receive(self) -> MCPMessage | None:
        """Receive message from stdin (non-blocking)."""
        import sys
        if self._closed:
            return None
        try:
            if sys.stdin.isatty():
                return None
            line = sys.stdin.readline()
            if not line:
                return None
            data = json.loads(line.strip())
            return MCPMessage(
                jsonrpc=data.get("jsonrpc", "2.0"),
                method=data.get("method", ""),
                params=data.get("params"),
                id=data.get("id"),
            )
        except (json.JSONDecodeError, EOFError):
            return None

    def close(self) -> None:
        """Close the transport."""
        self._closed = True


class HTTPTransport(Transport):
    """HTTP transport for remote MCP servers."""

    def __init__(self, base_url: str, headers: dict[str, str] | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = headers or {}
        self._closed = False

    def send(self, message: MCPMessage) -> None:
        """Send message via HTTP POST."""
        import urllib.request
        import urllib.error

        if self._closed:
            return

        payload = {
            "jsonrpc": message.jsonrpc,
            "method": message.method,
            "params": message.params or {},
            "id": message.id,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url}/mcp",
            data=data,
            headers=self._headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                logger.debug("HTTP response: %s", resp.status)
        except urllib.error.URLError as e:
            logger.error("HTTP send error: %s", e.reason)

    def receive(self) -> MCPMessage | None:
        """HTTP receive not implemented for client transport."""
        return None

    def close(self) -> None:
        """Close the transport."""
        self._closed = True


def create_transport(mode: str = "stdio", **kwargs: Any) -> Transport:
    """Factory for creating MCP transports."""
    if mode == "stdio":
        return StdioTransport()
    elif mode == "http":
        return HTTPTransport(
            base_url=kwargs.get("base_url", "http://localhost:8080"),
            headers=kwargs.get("headers"),
        )
    else:
        raise ValueError(f"Unknown transport mode: {mode}")