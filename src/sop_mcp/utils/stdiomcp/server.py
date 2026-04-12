"""Lightweight MCP server — stdio transport only, zero C-dependencies.

Implements JSON-RPC 2.0 over stdin/stdout per the MCP specification.
Provides the same public API as ``fastmcp.FastMCP`` so tool modules
can be used without changes.  The class is called ``StdioMCP``.
"""

from __future__ import annotations

import inspect
import json
import logging
import sys
from typing import Any, Callable, get_type_hints

logger = logging.getLogger(__name__)

# MCP protocol version
PROTOCOL_VERSION = "2024-11-05"

# JSON schema type mapping
_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def _build_input_schema(fn: Callable) -> dict[str, Any]:
    """Build a JSON Schema ``inputSchema`` from a function's signature."""
    sig = inspect.signature(fn)
    hints = get_type_hints(fn)
    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        hint = hints.get(name, str)
        # Unwrap Optional / X | None
        origin = getattr(hint, "__origin__", None)
        args = getattr(hint, "__args__", ())
        is_optional = False
        if origin is type(int | str):  # types.UnionType (3.10+)
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                hint = non_none[0]
                is_optional = True

        json_type = _TYPE_MAP.get(hint, "string")
        prop: dict[str, Any] = {"type": json_type}

        # Extract description from Annotated metadata or Field
        ann = hints.get(name)
        if hasattr(ann, "__metadata__"):
            for meta in ann.__metadata__:
                if isinstance(meta, str):
                    prop["description"] = meta
                elif hasattr(meta, "description") and meta.description:
                    prop["description"] = meta.description

        properties[name] = prop
        if param.default is inspect.Parameter.empty and not is_optional:
            required.append(name)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


class _ToolInfo:
    """Internal tool registration."""

    __slots__ = ("name", "description", "fn", "input_schema")

    def __init__(self, name: str, description: str, fn: Callable, input_schema: dict[str, Any]) -> None:
        self.name = name
        self.description = description
        self.fn = fn
        self.input_schema = input_schema


class _ResourceInfo:
    """Internal resource registration."""

    __slots__ = ("uri", "name", "description", "mime_type", "fn")

    def __init__(self, uri: str, name: str, description: str, mime_type: str, fn: Callable) -> None:
        self.uri = uri
        self.name = name
        self.description = description
        self.mime_type = mime_type
        self.fn = fn


class StdioMCP:
    """Lightweight MCP server — stdio only, zero C-dependencies.

    Supports tool and resource registration via decorators, and runs
    a JSON-RPC 2.0 event loop over stdio.
    """

    def __init__(self, name: str = "MCP Server", **kwargs: Any) -> None:
        self.name = name
        self._tools: dict[str, _ToolInfo] = {}
        self._resources: dict[str, _ResourceInfo] = {}

    # ------------------------------------------------------------------
    # Registration API (matches fastmcp)
    # ------------------------------------------------------------------

    def tool(self, name: str | None = None, description: str | None = None) -> Callable:
        """Register a function as an MCP tool (decorator factory)."""

        def decorator(fn: Callable) -> Callable:
            tool_name = name or fn.__name__
            # Prefer explicit description, then @tool() meta, then docstring
            desc = description
            if desc is None and hasattr(fn, "_tool_meta"):
                desc = fn._tool_meta.get("description")
            if desc is None:
                desc = (fn.__doc__ or "").strip().split("\n")[0]
            schema = _build_input_schema(fn)
            self._tools[tool_name] = _ToolInfo(tool_name, desc or "", fn, schema)
            return fn

        return decorator

    def resource(
        self,
        uri: str,
        name: str = "",
        description: str = "",
        mime_type: str = "text/plain",
    ) -> Callable:
        """Register a function as an MCP resource (decorator factory)."""

        def decorator(fn: Callable) -> Callable:
            self._resources[uri] = _ResourceInfo(uri, name, description, mime_type, fn)
            return fn

        return decorator

    # ------------------------------------------------------------------
    # Programmatic access (used by tests and hook middleware)
    # ------------------------------------------------------------------

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a registered tool by name. Returns JSON-serialisable result."""
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")
        tool = self._tools[name]
        args = arguments or {}
        # Coerce types from JSON (everything arrives as string over wire)
        result = tool.fn(**args)
        return json.dumps(result)

    async def list_tools(self) -> list[Any]:
        """Return tool descriptors (used by tests)."""
        return [
            type("Tool", (), {"name": t.name, "description": t.description, "inputSchema": t.input_schema})()
            for t in self._tools.values()
        ]

    async def list_resources(self) -> list[Any]:
        """Return resource descriptors (used by tests)."""
        return [
            type(
                "Resource",
                (),
                {"uri": r.uri, "name": r.name, "description": r.description, "mimeType": r.mime_type},
            )()
            for r in self._resources.values()
        ]

    async def read_resource(self, uri: str) -> str:
        """Read a resource by URI."""
        if uri not in self._resources:
            raise ValueError(f"Unknown resource: {uri}")
        return self._resources[uri].fn()

    # ------------------------------------------------------------------
    # JSON-RPC stdio transport
    # ------------------------------------------------------------------

    def run(self, transport: str = "stdio") -> None:
        """Start the MCP server on stdio."""
        if transport != "stdio":
            raise ValueError(f"Only stdio transport is supported, got: {transport}")
        logger.info("Starting %s (lite stdio)", self.name)
        self._stdio_loop()

    def _stdio_loop(self) -> None:
        """Read JSON-RPC requests from stdin, write responses to stdout."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                self._write_error(None, -32700, "Parse error")
                continue

            req_id = request.get("id")
            method = request.get("method", "")
            params = request.get("params", {})

            # Notifications (no id) — just acknowledge
            if req_id is None:
                continue

            response = self._handle_request(method, params, req_id)
            if response is not None:
                self._write(response)

    def _handle_request(self, method: str, params: dict[str, Any], req_id: Any) -> dict[str, Any] | None:
        """Dispatch a JSON-RPC method."""
        if method == "initialize":
            return self._rpc_result(
                req_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False},
                    },
                    "serverInfo": {"name": self.name, "version": "1.0.0"},
                },
            )

        if method == "ping":
            return self._rpc_result(req_id, {})

        if method == "tools/list":
            tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.input_schema,
                }
                for t in self._tools.values()
            ]
            return self._rpc_result(req_id, {"tools": tools})

        if method == "tools/call":
            return self._handle_tool_call(params, req_id)

        if method == "resources/list":
            resources = [
                {
                    "uri": r.uri,
                    "name": r.name,
                    "description": r.description,
                    "mimeType": r.mime_type,
                }
                for r in self._resources.values()
            ]
            return self._rpc_result(req_id, {"resources": resources})

        if method == "resources/read":
            return self._handle_resource_read(params, req_id)

        return self._rpc_error(req_id, -32601, f"Method not found: {method}")

    def _handle_tool_call(self, params: dict[str, Any], req_id: Any) -> dict[str, Any]:
        """Handle tools/call."""
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        if name not in self._tools:
            return self._rpc_error(req_id, -32602, f"Unknown tool: {name}")

        try:
            result = self._tools[name].fn(**arguments)
            content = [{"type": "text", "text": json.dumps(result)}]
            return self._rpc_result(req_id, {"content": content})
        except Exception as e:
            content = [{"type": "text", "text": json.dumps({"error": str(e)})}]
            return self._rpc_result(req_id, {"content": content, "isError": True})

    def _handle_resource_read(self, params: dict[str, Any], req_id: Any) -> dict[str, Any]:
        """Handle resources/read."""
        uri = params.get("uri", "")
        if uri not in self._resources:
            return self._rpc_error(req_id, -32602, f"Unknown resource: {uri}")

        try:
            text = self._resources[uri].fn()
            contents = [{"uri": uri, "mimeType": self._resources[uri].mime_type, "text": text}]
            return self._rpc_result(req_id, {"contents": contents})
        except Exception as e:
            return self._rpc_error(req_id, -32603, str(e))

    # ------------------------------------------------------------------
    # JSON-RPC helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rpc_result(req_id: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    @staticmethod
    def _rpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    @staticmethod
    def _write(response: dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

    @staticmethod
    def _write_error(req_id: Any, code: int, message: str) -> None:
        resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()
