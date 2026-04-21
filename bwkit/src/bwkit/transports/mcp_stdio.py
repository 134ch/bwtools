"""MCP stdio server — the primary Phase 1 integration surface.

Every enabled tool in the registry is advertised as one MCP tool using its
auto-generated JSON Schema. Calls funnel through Runner so metrics, error
classification, and validation are uniform with the CLI path.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from bwkit.core.config import load as load_config
from bwkit.core.errors import BwkitError
from bwkit.core.metrics import Metrics
from bwkit.core.registry import load_registry
from bwkit.core.runner import Runner


def _caller_for(client_info: Any) -> str:
    name = getattr(client_info, "name", None) if client_info is not None else None
    return name or "mcp-unknown"


async def _serve_async() -> None:
    registry = load_registry(config=load_config())
    metrics = Metrics()
    runner = Runner(registry=registry, metrics=metrics)

    server: Server = Server("bwkit")

    @server.list_tools()
    async def list_tools() -> list[Tool]:  # type: ignore[misc]
        out: list[Tool] = []
        for name, resolved in registry.items():
            if not resolved.enabled:
                continue
            out.append(Tool(
                name=name,
                description=resolved.spec.summary,
                inputSchema=resolved.spec.input_schema or {"type": "object", "properties": {}},
            ))
        return out

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:  # type: ignore[misc]
        caller = _caller_for(getattr(server.request_context, "client_info", None))
        try:
            result = runner.call(
                name,
                caller=caller,
                transport="mcp_stdio",
                arguments=arguments or {},
            )
        except BwkitError as e:
            payload = {"ok": False, "error_code": e.code, "message": str(e)}
            return [TextContent(type="text", text=json.dumps(payload))]

        payload = {"ok": True, "result": result}
        return [TextContent(type="text", text=json.dumps(payload, default=str))]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="bwkit",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def serve() -> None:
    """Blocking entrypoint for `bwkit mcp`."""
    asyncio.run(_serve_async())
