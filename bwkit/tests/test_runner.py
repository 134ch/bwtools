from __future__ import annotations

import pytest

from bwkit.core.errors import (
    InvalidArgumentsError,
    MissingExtraError,
    ToolDisabledError,
    UnknownToolError,
)
from bwkit.core.metrics import Metrics
from bwkit.core.registry import load_registry
from bwkit.core.config import UserConfig
from bwkit.core.runner import Runner


def _runner(overrides=None) -> Runner:
    reg = load_registry(config=UserConfig(overrides=overrides or {}))
    return Runner(registry=reg, metrics=Metrics())


def test_unknown_tool_is_classified(bwkit_home):
    r = _runner()
    with pytest.raises(UnknownToolError) as exc:
        r.call("no_such_tool", caller="cli", transport="cli", arguments={})
    assert exc.value.code == "unknown_tool"
    rows = r.metrics.recent(limit=1)
    assert rows[0]["status"] == "error"
    assert rows[0]["error_code"] == "unknown_tool"
    assert rows[0]["transport"] == "cli"


def test_disabled_tool_is_classified(bwkit_home):
    r = _runner(overrides={"markitdown": False})
    with pytest.raises(ToolDisabledError) as exc:
        r.call("markitdown", caller="cli", transport="cli", arguments={"source": "x"})
    assert exc.value.code == "tool_disabled"


def test_invalid_arguments_classified(bwkit_home):
    r = _runner()
    with pytest.raises(InvalidArgumentsError):
        r.call("markitdown", caller="cli", transport="cli", arguments={"bogus": 1})
    rows = r.metrics.recent(limit=1)
    assert rows[0]["error_code"] == "invalid_arguments"


def test_missing_extra_classified(bwkit_home, monkeypatch):
    # Simulate the `markitdown` package not being importable.
    import builtins
    real_import = builtins.__import__

    def sabotage(name, *a, **kw):
        if name == "markitdown":
            raise ImportError("simulated: markitdown not installed")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", sabotage)

    r = _runner()
    with pytest.raises(MissingExtraError) as exc:
        r.call(
            "markitdown",
            caller="cli",
            transport="cli",
            arguments={"source": "/tmp/nope.html"},
        )
    assert exc.value.code == "missing_extra"
    rows = r.metrics.recent(limit=1)
    assert rows[0]["error_code"] == "missing_extra"
    assert rows[0]["caller"] == "cli"
    assert rows[0]["transport"] == "cli"
