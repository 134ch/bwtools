"""Per-user mutable configuration at ~/.bwkit/config.toml.

The packaged catalog.yaml is read-only metadata. This module handles the
user-owned override file. Only keys under [enabled] are honored today; any
override pointing at a name not in the shipped catalog is warned about (at
registry load time), never errored on.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

from .creds import _bwkit_home


@dataclass
class UserConfig:
    overrides: dict[str, bool] = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


def config_path() -> Path:
    return _bwkit_home() / "config.toml"


def ensure_home() -> Path:
    home = _bwkit_home()
    home.mkdir(parents=True, exist_ok=True)
    return home


def load() -> UserConfig:
    path = config_path()
    if not path.exists():
        return UserConfig()
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return UserConfig()
    overrides = {k: bool(v) for k, v in (raw.get("enabled") or {}).items()}
    return UserConfig(overrides=overrides, raw=raw)


def set_enabled(tool: str, value: bool) -> None:
    """Persist `[enabled].<tool> = value` to config.toml (creates the file)."""
    ensure_home()
    path = config_path()
    # Read existing (plain text; we don't round-trip TOML with tomllib).
    cfg = load()
    cfg.overrides[tool] = value

    lines = ["# bwkit per-user config. See README for the full schema.", "", "[enabled]"]
    for k in sorted(cfg.overrides):
        lines.append(f"{k} = {'true' if cfg.overrides[k] else 'false'}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
