from __future__ import annotations

import warnings

import pytest

from bwkit.core.config import UserConfig
from bwkit.core.registry import load_registry


def test_override_disables_default_enabled_tool(bwkit_home):
    reg = load_registry(config=UserConfig(overrides={"markitdown": False}))
    assert reg["markitdown"].enabled is False


def test_stale_override_emits_warning_not_error(bwkit_home):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        reg = load_registry(config=UserConfig(overrides={"nonexistent_tool": True}))
    assert "markitdown" in reg
    assert any(
        "nonexistent_tool" in str(item.message) and "ignored" in str(item.message)
        for item in w
    ), f"expected stale-override warning, got: {[str(i.message) for i in w]}"
