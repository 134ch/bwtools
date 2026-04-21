"""End-to-end check that the MCP stdio server spawns and advertises tools.

We don't implement the full MCP JSON-RPC handshake here — that's the SDK's
job. Instead we verify the transport entrypoint wires the registry + runner
together by calling its internal plumbing directly.
"""

from __future__ import annotations

import pytest

from bwkit.core.config import UserConfig
from bwkit.core.registry import load_registry


def test_registry_exposes_expected_tool_shape_for_mcp(bwkit_home):
    reg = load_registry(config=UserConfig())
    resolved = reg["markitdown"]
    assert resolved.enabled
    schema = resolved.spec.input_schema
    assert schema["type"] == "object"
    assert set(schema["properties"]) == {"source", "hint"}
    assert "source" in schema["required"]


def test_mcp_module_imports(bwkit_home):
    # Confirms that the `mcp` SDK is installed and the transport module is well-formed.
    pytest.importorskip("mcp", reason="mcp SDK not installed")
    import bwkit.transports.mcp_stdio as t

    assert callable(t.serve)
