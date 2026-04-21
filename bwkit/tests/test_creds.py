from __future__ import annotations

import pytest

from bwkit.core.creds import declared_status, get
from bwkit.core.errors import MissingCredentialError


def test_env_var_wins_over_dotenv(bwkit_home, monkeypatch):
    (bwkit_home / ".env").write_text("FOO=from_dotenv\n", encoding="utf-8")
    monkeypatch.setenv("FOO", "from_env")
    assert get("FOO") == "from_env"


def test_dotenv_used_when_env_absent(bwkit_home, monkeypatch):
    (bwkit_home / ".env").write_text("BAR=from_dotenv\n", encoding="utf-8")
    monkeypatch.delenv("BAR", raising=False)
    assert get("BAR") == "from_dotenv"


def test_missing_required_raises(bwkit_home, monkeypatch):
    monkeypatch.delenv("NOPE_NOT_SET", raising=False)
    with pytest.raises(MissingCredentialError) as exc:
        get("NOPE_NOT_SET")
    assert exc.value.code == "missing_credential"
    assert exc.value.var == "NOPE_NOT_SET"


def test_missing_optional_returns_none(bwkit_home, monkeypatch):
    monkeypatch.delenv("ALSO_NOT_SET", raising=False)
    assert get("ALSO_NOT_SET", required=False) is None


def test_declared_status_mixed(bwkit_home, monkeypatch):
    (bwkit_home / ".env").write_text("FROM_FILE=1\n", encoding="utf-8")
    monkeypatch.setenv("FROM_ENV", "1")
    monkeypatch.delenv("NEITHER", raising=False)
    status = declared_status(("FROM_FILE", "FROM_ENV", "NEITHER"))
    assert status == {"FROM_FILE": True, "FROM_ENV": True, "NEITHER": False}
