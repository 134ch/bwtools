from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .bwagent import bwagent_doctor
from .paths import find_repo_root
from .tools import (
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    DEFAULT_CODEX_ROUTER_PORT,
    codex_router_start,
    codex_router_status,
    codex_router_stop,
    convert_markitdown,
    get_tool,
    tool_inventory,
)


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def make_handler(repo_root: Path) -> type[BaseHTTPRequestHandler]:
    class BwtoolsHandler(BaseHTTPRequestHandler):
        server_version = f"bwtools-api/{__version__}"

        def log_message(self, format: str, *args: Any) -> None:
            # Keep the service quiet when agents call it repeatedly.
            return

        def _send_json(self, payload: Any, status: int = 200) -> None:
            body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_error_json(self, status: int, message: str) -> None:
            self._send_json({"ok": False, "error": message}, status)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length == 0:
                return {}
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON body: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            return payload

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)

            try:
                if path in {"/", "/health"}:
                    self._send_json(
                        {
                            "ok": True,
                            "service": "bwtools-api",
                            "version": __version__,
                            "repo_root": str(repo_root),
                        }
                    )
                    return

                if path == "/tools":
                    self._send_json(tool_inventory(repo_root))
                    return

                if path == "/tools/codex-router/status":
                    port = _as_int(
                        (query.get("port") or [None])[0],
                        DEFAULT_CODEX_ROUTER_PORT,
                    )
                    self._send_json(codex_router_status(repo_root, port))
                    return

                if path == "/tools/bwagent-support/doctor":
                    result = bwagent_doctor(
                        repo_root,
                        (query.get("ops_root") or [None])[0],
                        probe_webui=not _as_bool(
                            (query.get("skip_webui") or [None])[0],
                            False,
                        ),
                        webui_timeout=float(
                            (query.get("webui_timeout") or [2.0])[0],
                        ),
                    )
                    self._send_json(result)
                    return

                if path.startswith("/tools/"):
                    name = path.removeprefix("/tools/")
                    tool = get_tool(name, repo_root)
                    if tool is None:
                        self._send_error_json(HTTPStatus.NOT_FOUND, "Tool not found")
                    else:
                        self._send_json(tool)
                    return

                self._send_error_json(HTTPStatus.NOT_FOUND, "Not found")
            except Exception as exc:  # noqa: BLE001 - local API reports details
                self._send_error_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    f"{type(exc).__name__}: {exc}",
                )

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"

            try:
                payload = self._read_json()

                if path == "/tools/codex-router/start":
                    result = codex_router_start(
                        repo_root,
                        public=_as_bool(payload.get("public"), False),
                        host=payload.get("host"),
                        port=_as_int(
                            payload.get("port"),
                            DEFAULT_CODEX_ROUTER_PORT,
                        ),
                        no_wait=_as_bool(payload.get("no_wait"), False),
                        timeout=_as_int(payload.get("timeout"), 90),
                    )
                    self._send_json(result, 200 if result.get("ok") else 500)
                    return

                if path == "/tools/codex-router/stop":
                    process_id = payload.get("process_id")
                    result = codex_router_stop(
                        repo_root,
                        process_id=int(process_id) if process_id else None,
                        timeout=_as_int(payload.get("timeout"), 30),
                    )
                    self._send_json(result, 200 if result.get("ok") else 500)
                    return

                if path == "/tools/markitdown/convert":
                    if not payload.get("input_path"):
                        self._send_error_json(
                            HTTPStatus.BAD_REQUEST,
                            "input_path is required",
                        )
                        return
                    result = convert_markitdown(
                        payload["input_path"],
                        payload.get("output_path"),
                        include_markdown=_as_bool(
                            payload.get("include_markdown"),
                            True,
                        ),
                        repo_root=repo_root,
                    )
                    self._send_json({"ok": True, **result})
                    return

                self._send_error_json(HTTPStatus.NOT_FOUND, "Not found")
            except ValueError as exc:
                self._send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
            except Exception as exc:  # noqa: BLE001 - local API reports details
                self._send_error_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    f"{type(exc).__name__}: {exc}",
                )

    return BwtoolsHandler


def run_server(
    host: str = DEFAULT_API_HOST,
    port: int = DEFAULT_API_PORT,
    repo_root: str | Path | None = None,
) -> None:
    root = find_repo_root(repo_root)
    handler = make_handler(root)
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"bwtools-api listening on http://{host}:{port}")
    print(f"repo root: {root}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
