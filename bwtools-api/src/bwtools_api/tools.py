from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .paths import find_repo_root

DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 2480
DEFAULT_CODEX_ROUTER_PORT = 2455


def tool_inventory(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = find_repo_root(repo_root)
    tools = [
        {
            "name": "bwtools-api",
            "status": "active",
            "kind": "first-party-api",
            "path": str(root / "bwtools-api"),
            "commands": [
                "bwtools server",
                "bwtools tools",
                "bwtools codex-router status",
                "bwtools markitdown convert <input> --output <output>",
            ],
            "http_endpoints": [
                "GET /health",
                "GET /tools",
                "GET /tools/{name}",
                "GET /tools/codex-router/status",
                "POST /tools/codex-router/start",
                "POST /tools/codex-router/stop",
                "POST /tools/markitdown/convert",
            ],
        },
        {
            "name": "codex-router",
            "status": "active",
            "kind": "router",
            "path": str(root / "codex-router"),
            "local_url": f"http://127.0.0.1:{DEFAULT_CODEX_ROUTER_PORT}",
            "openai_base_url": f"http://127.0.0.1:{DEFAULT_CODEX_ROUTER_PORT}/v1",
            "codex_base_url": (
                f"http://127.0.0.1:{DEFAULT_CODEX_ROUTER_PORT}/backend-api/codex"
            ),
            "commands": [
                "bwtools codex-router status",
                "bwtools codex-router start",
                "bwtools codex-router stop",
            ],
        },
        {
            "name": "markitdown",
            "status": "active",
            "kind": "document-converter",
            "path": str(root / "markitdown"),
            "commands": [
                "bwtools markitdown convert <input>",
                "bwtools markitdown convert <input> --output <output>",
            ],
        },
        {
            "name": "yt-transcripts",
            "status": "planned",
            "kind": "transcript-extractor",
            "path": str(root / "yt-transcripts"),
            "commands": [],
        },
    ]
    return {"repo_root": str(root), "tools": tools}


def get_tool(name: str, repo_root: str | Path | None = None) -> dict[str, Any] | None:
    for tool in tool_inventory(repo_root)["tools"]:
        if tool["name"] == name:
            return tool
    return None


def probe_url(url: str, timeout: float = 2.0) -> dict[str, Any]:
    started = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            elapsed_ms = round((time.monotonic() - started) * 1000)
            return {
                "ok": 200 <= response.status < 400,
                "status_code": response.status,
                "elapsed_ms": elapsed_ms,
                "url": url,
            }
    except urllib.error.HTTPError as exc:
        elapsed_ms = round((time.monotonic() - started) * 1000)
        return {
            "ok": False,
            "status_code": exc.code,
            "elapsed_ms": elapsed_ms,
            "url": url,
            "error": str(exc),
        }
    except Exception as exc:  # noqa: BLE001 - surfaced in local status JSON
        elapsed_ms = round((time.monotonic() - started) * 1000)
        return {
            "ok": False,
            "elapsed_ms": elapsed_ms,
            "url": url,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _process_exists(pid: int) -> bool:
    if pid <= 0:
        return False

    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception:
            return False
        output = result.stdout.strip()
        return str(pid) in output and "No tasks" not in output

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def codex_router_status(
    repo_root: str | Path | None = None,
    port: int = DEFAULT_CODEX_ROUTER_PORT,
) -> dict[str, Any]:
    root = find_repo_root(repo_root)
    runtime_root = root / "codex-router" / "codex-lb-data"
    pid_file = runtime_root / "codex-lb.pid"
    pid: int | None = None
    pid_raw: str | None = None

    if pid_file.is_file():
        pid_raw = pid_file.read_text(encoding="utf-8", errors="replace").strip()
        try:
            pid = int(pid_raw)
        except ValueError:
            pid = None

    health_url = f"http://127.0.0.1:{port}/health/live"
    health = probe_url(health_url)

    return {
        "name": "codex-router",
        "port": port,
        "local_url": f"http://127.0.0.1:{port}",
        "openai_base_url": f"http://127.0.0.1:{port}/v1",
        "codex_base_url": f"http://127.0.0.1:{port}/backend-api/codex",
        "runtime_root": str(runtime_root),
        "pid_file": str(pid_file),
        "pid_file_exists": pid_file.is_file(),
        "pid": pid,
        "pid_raw": pid_raw,
        "process_running": _process_exists(pid) if pid is not None else False,
        "health": health,
        "ok": bool(health.get("ok")),
    }


def _powershell_executable() -> str:
    if os.name == "nt":
        return "powershell.exe"
    return shutil.which("pwsh") or shutil.which("powershell") or "pwsh"


def _run_script(
    script: Path,
    args: list[str],
    cwd: Path,
    timeout: int,
) -> dict[str, Any]:
    command = [
        _powershell_executable(),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        *args,
    ]
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        elapsed_ms = round((time.monotonic() - started) * 1000)
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "elapsed_ms": elapsed_ms,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "command": command,
        }
    except Exception as exc:  # noqa: BLE001 - local API reports command errors
        elapsed_ms = round((time.monotonic() - started) * 1000)
        return {
            "ok": False,
            "elapsed_ms": elapsed_ms,
            "error": f"{type(exc).__name__}: {exc}",
            "command": command,
        }


def codex_router_start(
    repo_root: str | Path | None = None,
    *,
    public: bool = False,
    host: str | None = None,
    port: int = DEFAULT_CODEX_ROUTER_PORT,
    no_wait: bool = False,
    timeout: int = 90,
) -> dict[str, Any]:
    root = find_repo_root(repo_root)
    script = root / "codex-router" / "bin" / "start.ps1"
    args = ["-Port", str(port)]
    if host:
        args.extend(["-HostAddress", host])
    if public:
        args.append("-Public")
    if no_wait:
        args.append("-NoWait")

    result = _run_script(script, args, root / "codex-router", timeout)
    result["status"] = codex_router_status(root, port)
    return result


def codex_router_stop(
    repo_root: str | Path | None = None,
    *,
    process_id: int | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    root = find_repo_root(repo_root)
    script = root / "codex-router" / "bin" / "stop.ps1"
    args: list[str] = []
    if process_id is not None:
        args.extend(["-ProcessId", str(process_id)])

    result = _run_script(script, args, root / "codex-router", timeout)
    result["status"] = codex_router_status(root)
    return result


def _ensure_markitdown_import(repo_root: Path) -> None:
    package_src = repo_root / "markitdown" / "upstream" / "packages" / "markitdown" / "src"
    if package_src.is_dir():
        sys.path.insert(0, str(package_src))


def convert_markitdown(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    include_markdown: bool = True,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    root = find_repo_root(repo_root)
    source = Path(input_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Input file does not exist: {source}")

    _ensure_markitdown_import(root)
    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise RuntimeError(
            "Could not import markitdown. Run `python -m pip install -r "
            "requirements.txt` from the bwtools repo root."
        ) from exc

    result = MarkItDown().convert(str(source))
    markdown = result.text_content

    payload: dict[str, Any] = {
        "input_path": str(source),
        "characters": len(markdown),
        "output_path": None,
    }

    if output_path:
        target = Path(output_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markdown, encoding="utf-8")
        payload["output_path"] = str(target)

    if include_markdown:
        payload["markdown"] = markdown

    return payload
