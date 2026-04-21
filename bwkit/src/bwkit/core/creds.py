"""BYOK credential access.

- Read process env first, then overlay ~/.bwkit/.env (process env wins).
- Tools call `get("VAR")` inside their run() — never from the runner.
- Secrets never pass through tool kwargs, so they never reach input_hash or logs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values

from .errors import MissingCredentialError


def _bwkit_home() -> Path:
    # Honor $BWKIT_HOME for tests; otherwise ~/.bwkit/.
    override = os.environ.get("BWKIT_HOME")
    if override:
        return Path(override)
    return Path.home() / ".bwkit"


def _load_env_file() -> dict[str, str]:
    path = _bwkit_home() / ".env"
    if not path.exists():
        return {}
    # dotenv_values returns dict[str, Optional[str]]; drop Nones.
    return {k: v for k, v in dotenv_values(path).items() if v is not None}


def get(name: str, *, required: bool = True) -> Optional[str]:
    """Return credential `name` or raise/return None if missing."""
    value = os.environ.get(name)
    if value is None:
        value = _load_env_file().get(name)
    if value is None and required:
        raise MissingCredentialError(var=name)
    return value


def declared_status(env_vars: tuple[str, ...]) -> dict[str, bool]:
    """For `bwkit doctor`: which declared vars are set (from env or .env)?"""
    file_vars = _load_env_file()
    return {
        v: (v in os.environ) or (v in file_vars)
        for v in env_vars
    }
