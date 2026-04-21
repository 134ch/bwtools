"""Shared fixtures: isolate ~/.bwkit/ per test via BWKIT_HOME."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def bwkit_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "bwkit_home"
    home.mkdir()
    monkeypatch.setenv("BWKIT_HOME", str(home))
    # Also clear vars bwkit might read so tests don't pick them up from the dev machine.
    for var in list(os.environ):
        if var.startswith("BWKIT_TEST_"):
            monkeypatch.delenv(var, raising=False)
    return home
