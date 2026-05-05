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
from collections.abc import Callable
from typing import Any, get_type_hints

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
    hints = get_type_hints(fn, include_extras=True)
    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        hint = hints.get(name, str)
        description: str | None = None

        # Extract metadata from Annotated types.
        if hasattr(hint, "__metadata__"):
            for meta in hint.__metadata__:
                if isinstance(meta, str):
                    description = meta
                elif hasattr(meta, "description") and meta.description:
                    description = meta.description
            # Unwrap Annotated to get the base type.
            hint = hint.__args__[0] if hasattr(hint, "__args__") else hint

        # Handle Optional (Union with None) / UnionType (3.10+).
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
        if description:
            prop["description"] = description

        properties[name] = prop
        if param.default is inspect.Parameter.empty and not is_optional:
            required.append(name)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


class _ToolInfo:
    """Internal tool registration."""

    __slots__ = ("description", "fn", "input_schema", "name")

    def __init__(self, name: str, description: str, fn: Callable, input_schema: dict[str, Any]) -> None:
        self.name = name
        self.description = description
        self.fn = fn
        self.input_schema = input_schema


class _ResourceInfo:
    """Internal resource registration."""

    __slots__ = ("description", "fn", "is_binary", "mime_type", "name", "uri")

    def __init__(
        self,
        uri: str,
        name: str,
        description: str,
        mime_type: str,
        fn: Callable,
        is_binary: bool = False,
    ) -> None:
        self.uri = uri
        self.name = name
        self.description = description
        self.mime_type = mime_type
        self.fn = fn
        self.is_binary = is_binary


class StdioMCP:
    """Lightweight MCP server — stdio only, zero C-dependencies."""

    def __init__(
        self, name: str = "MCP Server", resources_as_tools: bool = True, instructions: str = "", **kwargs: Any
    ) -> None:
        self.name = name
        self.instructions = instructions
        self._tools: dict[str, _ToolInfo] = {}
        self._resources: dict[str, _ResourceInfo] = {}
        self._subscriptions: set[str] = set()
        self._resources_as_tools = resources_as_tools
        self._resource_tools_registered = False

    # ------------------------------------------------------------------
    # Registration API (matches fastmcp)
    # ------------------------------------------------------------------

    def tool(self, name: str | None = None, description: str | None = None) -> Callable:
        """Register a function as an MCP tool (decorator factory)."""

        def decorator(fn: Callable) -> Callable:
            tool_name = name or fn.__name__
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
        is_binary: bool = False,
    ) -> Callable:
        """Register a function as an MCP resource (decorator factory)."""

        def decorator(fn: Callable) -> Callable:
            self._resources[uri] = _ResourceInfo(uri, name, description, mime_type, fn, is_binary)
            return fn

        return decorator

    # ------------------------------------------------------------------
    # Programmatic access (used by tests and hook middleware)
    # ------------------------------------------------------------------

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a registered tool by name. Returns JSON-serialisable result."""
        self._ensure_resource_tools()
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")
        tool = self._tools[name]
        args = arguments or {}
        result = tool.fn(**args)
        return json.dumps(result)

    async def list_tools(self) -> list[Any]:
        """Return tool descriptors (used by tests)."""
        self._ensure_resource_tools()
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

    def notify_resources_list_changed(self) -> None:
        """Emit a ``notifications/resources/list_changed`` message to the client."""
        self._emit_notification({"jsonrpc": "2.0", "method": "notifications/resources/list_changed"})

    def notify_resource_updated(self, uri: str) -> None:
        """Emit ``notifications/resources/updated`` for a subscribed URI only."""
        if uri not in self._subscriptions:
            return
        self._emit_notification(
            {
                "jsonrpc": "2.0",
                "method": "notifications/resources/updated",
                "params": {"uri": uri},
            }
        )

    def _emit_notification(self, notification: dict[str, Any]) -> None:
        """Write a notification to stdout (best-effort)."""
        try:
            sys.stdout.write(json.dumps(notification) + "\n")
            sys.stdout.flush()
        except (BrokenPipeError, ValueError):
            logger.debug("Could not emit notification")

    # ------------------------------------------------------------------
    # JSON-RPC stdio transport
    # ------------------------------------------------------------------

    def run(self, transport: str = "stdio") -> None:
        """Start the MCP server on stdio."""
        if transport != "stdio":
            raise ValueError(f"Only stdio transport is supported, got: {transport}")
        self._ensure_resource_tools()
        logger.info("Starting %s (lite stdio)", self.name)
        self._stdio_loop()

    def _ensure_resource_tools(self) -> None:
        """Register resource tools if enabled and not yet registered."""
        if self._resources_as_tools and not self._resource_tools_registered and self._resources:
            self._register_resource_tools()
            self._resource_tools_registered = True

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

            if req_id is None:
                continue

            response = self._dispatch(method, params, req_id)
            if response is not None:
                self._write(response)

    # ------------------------------------------------------------------
    # Method dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, method: str, params: dict[str, Any], req_id: Any) -> dict[str, Any] | None:
        """Dispatch a JSON-RPC method to the appropriate handler."""
        dispatch_table: dict[str, Callable] = {
            "initialize": self._handle_initialize,
            "ping": self._handle_ping,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tool_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resource_read,
            "resources/subscribe": self._handle_subscribe,
            "resources/unsubscribe": self._handle_unsubscribe,
        }
        handler = dispatch_table.get(method)
        if handler is None:
            return self._rpc_error(req_id, -32601, f"Method not found: {method}")
        return handler(params, req_id)

    # Keep backward-compat alias for tests that call _handle_request directly
    _handle_request = _dispatch

    def _handle_initialize(self, params: dict[str, Any], req_id: Any) -> dict[str, Any]:
        result: dict[str, Any] = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": True, "listChanged": True},
            },
            "serverInfo": {"name": self.name, "version": "1.0.0"},
        }
        if self.instructions:
            result["instructions"] = self.instructions
        return self._rpc_result(req_id, result)

    def _handle_ping(self, params: dict[str, Any], req_id: Any) -> dict[str, Any]:
        return self._rpc_result(req_id, {})

    def _handle_tools_list(self, params: dict[str, Any], req_id: Any) -> dict[str, Any]:
        tools = [
            {"name": t.name, "description": t.description, "inputSchema": t.input_schema} for t in self._tools.values()
        ]
        return self._rpc_result(req_id, {"tools": tools})

    def _handle_tool_call(self, params: dict[str, Any], req_id: Any) -> dict[str, Any]:
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        if name not in self._tools:
            return self._rpc_error(req_id, -32602, f"Unknown tool: {name}")

        import asyncio

        try:
            result = asyncio.run(self.call_tool(name, arguments))
            content = [{"type": "text", "text": result}]
            return self._rpc_result(req_id, {"content": content})
        except Exception as e:
            content = [{"type": "text", "text": json.dumps({"error": str(e)})}]
            return self._rpc_result(req_id, {"content": content, "isError": True})

    def _handle_resources_list(self, params: dict[str, Any], req_id: Any) -> dict[str, Any]:
        resources = [
            {"uri": r.uri, "name": r.name, "description": r.description, "mimeType": r.mime_type}
            for r in self._resources.values()
        ]
        return self._rpc_result(req_id, {"resources": resources})

    def _handle_resource_read(self, params: dict[str, Any], req_id: Any) -> dict[str, Any]:
        uri = params.get("uri", "")
        if uri not in self._resources:
            return self._rpc_error(req_id, -32602, f"Unknown resource: {uri}")

        resource = self._resources[uri]
        try:
            payload = resource.fn()
        except Exception as e:
            return self._rpc_error(req_id, -32603, str(e))

        content: dict[str, Any] = {"uri": uri, "mimeType": resource.mime_type}
        if resource.is_binary:
            import base64

            if isinstance(payload, str):
                payload = payload.encode("utf-8")
            content["blob"] = base64.b64encode(payload).decode("ascii")
        else:
            content["text"] = payload
        return self._rpc_result(req_id, {"contents": [content]})

    def _handle_subscribe(self, params: dict[str, Any], req_id: Any) -> dict[str, Any]:
        uri = params.get("uri", "")
        if not uri:
            return self._rpc_error(req_id, -32602, "Missing 'uri' parameter")
        self._subscriptions.add(uri)
        return self._rpc_result(req_id, {})

    def _handle_unsubscribe(self, params: dict[str, Any], req_id: Any) -> dict[str, Any]:
        uri = params.get("uri", "")
        self._subscriptions.discard(uri)
        return self._rpc_result(req_id, {})

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

    def _register_resource_tools(self) -> None:
        """Auto-register list_resources and read_resource as tools."""
        resources = self._resources

        def _list() -> dict:
            return {
                "resources": [
                    {"uri": r.uri, "name": r.name, "description": r.description, "mimeType": r.mime_type}
                    for r in resources.values()
                ]
            }

        def _read(uri: str) -> dict:
            if uri not in resources:
                raise ValueError(f"Unknown resource URI: {uri}. Use list_resources to see available URIs.")
            r = resources[uri]
            return {"uri": uri, "mimeType": r.mime_type, "content": r.fn()}

        self.tool(
            name="list_resources",
            description="List all available resources with their URIs and descriptions.",
        )(_list)
        self.tool(
            name="read_resource",
            description="Read a resource by its URI.",
        )(_read)
