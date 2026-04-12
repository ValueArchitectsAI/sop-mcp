"""Test client for the lite MCP server — API-compatible with ``fastmcp.Client``."""

from __future__ import annotations

import json
from typing import Any


class Client:
    """In-process test client that calls the lite FastMCP server directly.

    Usage::

        async with Client(mcp) as client:
            result = await client.call_tool("run_sop", {"sop_name": "my_sop"})
    """

    def __init__(self, server: Any) -> None:
        self._server = server

    async def __aenter__(self) -> Client:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a tool and return the result."""
        result_json = await self._server.call_tool(name, arguments or {})
        return json.loads(result_json) if isinstance(result_json, str) else result_json

    async def list_tools(self) -> list[Any]:
        return await self._server.list_tools()

    async def list_resources(self) -> list[Any]:
        return await self._server.list_resources()

    async def read_resource(self, uri: str) -> str:
        return await self._server.read_resource(uri)
