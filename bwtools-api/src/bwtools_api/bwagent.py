from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from .paths import find_repo_root
from .tools import probe_url


def _default_ops_root(repo_root: Path) -> Path:
    configured = os.environ.get("BWAGENT_OPS_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return (repo_root.parent / "bwagent-ops").resolve()


def _check(name: str, status: str, message: str, **details: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": name, "status": status, "message": message}
    if details:
        payload["details"] = details
    return payload


def _clean_value(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("`") and cleaned.endswith("`"):
        return cleaned[1:-1].strip()
    return cleaned


def _fact_key(raw: str) -> str:
    key = raw.strip().lower()
    key = re.sub(r"[^a-z0-9]+", "_", key)
    return key.strip("_")


def _parse_setup_facts(text: str) -> dict[str, str]:
    facts: dict[str, str] = {}
    include_section = False
    relevant_sections = {
        "current live setup",
        "runtime assumptions",
        "current routing",
    }
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            section = stripped.removeprefix("## ").strip().lower()
            include_section = section in relevant_sections
            continue
        if not include_section:
            continue
        if not stripped.startswith("- ") or ":" not in stripped:
            continue
        key, value = stripped[2:].split(":", 1)
        value = _clean_value(value)
        if value:
            facts[_fact_key(key)] = value
    return facts


def _git_status(path: Path) -> dict[str, Any]:
    command = [
        "git",
        "-c",
        f"safe.directory={path.as_posix()}",
        "-C",
        str(path),
        "status",
        "--short",
        "--branch",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced in local doctor JSON
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "command": command,
        }

    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "command": command,
    }


def bwagent_doctor(
    repo_root: str | Path | None = None,
    ops_root: str | Path | None = None,
    *,
    probe_webui: bool = True,
    webui_timeout: float = 2.0,
) -> dict[str, Any]:
    """Run the first read-only bwagent-ops support check."""

    root = find_repo_root(repo_root)
    target = (
        Path(ops_root).expanduser().resolve()
        if ops_root is not None and str(ops_root).strip()
        else _default_ops_root(root)
    )
    setup_path = target / "ops" / "HERMES-SETUP.md"
    daily_prompt = target / "prompts" / "daily-operator-prompt.md"
    friction_backlog = target / "ops" / "FRICTION-BACKLOG.md"

    checks: list[dict[str, Any]] = []
    facts: dict[str, str] = {}

    if target.is_dir():
        checks.append(
            _check(
                "ops_root",
                "pass",
                "Found bwagent-ops workspace.",
                path=str(target),
            )
        )
    else:
        checks.append(
            _check(
                "ops_root",
                "fail",
                "Could not find bwagent-ops workspace.",
                path=str(target),
                env_var="BWAGENT_OPS_ROOT",
            )
        )

    if setup_path.is_file():
        setup_text = setup_path.read_text(encoding="utf-8", errors="replace")
        facts = _parse_setup_facts(setup_text)
        checks.append(
            _check(
                "hermes_setup_doc",
                "pass",
                "Found Hermes setup document.",
                path=str(setup_path),
            )
        )
    else:
        checks.append(
            _check(
                "hermes_setup_doc",
                "fail",
                "Missing ops/HERMES-SETUP.md.",
                path=str(setup_path),
            )
        )

    if daily_prompt.is_file():
        checks.append(
            _check(
                "daily_prompt",
                "pass",
                "Found daily operator prompt.",
                path=str(daily_prompt),
            )
        )
    else:
        checks.append(
            _check(
                "daily_prompt",
                "warn",
                "Missing daily operator prompt.",
                path=str(daily_prompt),
            )
        )

    if friction_backlog.is_file():
        checks.append(
            _check(
                "friction_backlog",
                "pass",
                "Found friction backlog.",
                path=str(friction_backlog),
            )
        )
    else:
        checks.append(
            _check(
                "friction_backlog",
                "warn",
                "Missing friction backlog.",
                path=str(friction_backlog),
            )
        )

    if target.is_dir():
        git = _git_status(target)
        if git.get("ok"):
            status_lines = [
                line
                for line in str(git.get("stdout", "")).splitlines()
                if line and not line.startswith("## ")
            ]
            checks.append(
                _check(
                    "ops_git_status",
                    "warn" if status_lines else "pass",
                    (
                        "bwagent-ops workspace has uncommitted changes."
                        if status_lines
                        else "bwagent-ops workspace is clean."
                    ),
                    git=git,
                )
            )
        else:
            checks.append(
                _check(
                    "ops_git_status",
                    "fail",
                    "Could not read bwagent-ops git status.",
                    git=git,
                )
            )

    webui_url = facts.get("active_webui_tailscale_url")
    if webui_url:
        checks.append(
            _check(
                "expected_webui_url",
                "pass",
                "Hermes setup document declares an active WebUI URL.",
                url=webui_url,
            )
        )
        if probe_webui:
            health_url = f"{webui_url.rstrip('/')}/health"
            health = probe_url(health_url, timeout=webui_timeout)
            checks.append(
                _check(
                    "webui_health",
                    "pass" if health.get("ok") else "warn",
                    (
                        "Hermes WebUI health endpoint responded."
                        if health.get("ok")
                        else "Hermes WebUI health endpoint did not respond cleanly."
                    ),
                    health=health,
                )
            )
    else:
        checks.append(
            _check(
                "expected_webui_url",
                "warn",
                "Hermes setup document does not declare active WebUI Tailscale URL.",
            )
        )

    counts = {
        "pass": sum(1 for check in checks if check["status"] == "pass"),
        "warn": sum(1 for check in checks if check["status"] == "warn"),
        "fail": sum(1 for check in checks if check["status"] == "fail"),
    }

    return {
        "ok": counts["fail"] == 0,
        "name": "bwagent doctor",
        "mode": "read-only-local",
        "repo_root": str(root),
        "ops_root": str(target),
        "facts": facts,
        "checks": checks,
        "summary": counts,
        "next_manual_vm_checks": [
            "systemctl status hermes-webui --no-pager",
            f"curl {webui_url.rstrip('/') + '/health' if webui_url else '<webui-url>/health'}",
            "hermes model",
            "git status --short --branch",
            "tailscale status",
        ],
    }
