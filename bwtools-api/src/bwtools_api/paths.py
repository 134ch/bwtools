from __future__ import annotations

import os
from pathlib import Path


def _looks_like_repo_root(path: Path) -> bool:
    return (
        (path / "AGENTS.md").is_file()
        and (path / "README.md").is_file()
        and (path / "codex-router").is_dir()
        and (path / "markitdown").is_dir()
    )


def _walk_up(start: Path) -> list[Path]:
    current = start if start.is_dir() else start.parent
    return [current, *current.parents]


def find_repo_root(explicit: str | Path | None = None) -> Path:
    """Find the bwtools checkout.

    Editable installs can discover the checkout from this package path. Installed
    console scripts run from elsewhere may need BWTOOLS_ROOT.
    """

    candidates: list[Path] = []

    if explicit:
        candidates.append(Path(explicit).expanduser())

    env_root = os.environ.get("BWTOOLS_ROOT")
    if env_root:
        candidates.append(Path(env_root).expanduser())

    candidates.extend(_walk_up(Path.cwd()))
    candidates.extend(_walk_up(Path(__file__).resolve()))

    for candidate in candidates:
        resolved = candidate.resolve()
        if _looks_like_repo_root(resolved):
            return resolved

    raise RuntimeError(
        "Could not find the bwtools repo root. Run from the repo or set "
        "BWTOOLS_ROOT to the checkout path."
    )
