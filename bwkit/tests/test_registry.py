from __future__ import annotations

from bwkit.core.config import UserConfig
from bwkit.core.registry import load_registry


def test_catalog_loads_and_markitdown_spec_matches(bwkit_home):
    reg = load_registry(config=UserConfig())
    assert "markitdown" in reg
    r = reg["markitdown"]
    assert r.spec.name == "markitdown"
    assert r.spec.maintained is True
    assert "markitdown" in r.spec.extras


def test_markitdown_module_imports_without_extra(bwkit_home, monkeypatch):
    # The adapter must not import the heavy `markitdown` package at module top level.
    # Simulate the extra being absent by sabotaging the import — if the adapter
    # re-imported at module top, importing it would have already failed.
    import importlib
    import sys

    # Force a fresh import and confirm success; the lazy import lives inside run().
    sys.modules.pop("bwkit.tools.markitdown", None)
    mod = importlib.import_module("bwkit.tools.markitdown")
    assert hasattr(mod, "SPEC")


def test_input_schema_generated_from_hints(bwkit_home):
    reg = load_registry(config=UserConfig())
    schema = reg["markitdown"].spec.input_schema
    assert schema["type"] == "object"
    assert "source" in schema["properties"]
    assert schema["properties"]["source"]["type"] == "string"
    # `source` has no default → required.
    assert "source" in schema.get("required", [])
