from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .server import run_server
from .tools import (
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    DEFAULT_CODEX_ROUTER_PORT,
    codex_router_start,
    codex_router_status,
    codex_router_stop,
    convert_markitdown,
    tool_inventory,
)


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _add_repo_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repo-root",
        help="bwtools checkout path. Defaults to auto-discovery or BWTOOLS_ROOT.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bwtools",
        description="Local API and CLI surface for bwtools.",
    )
    _add_repo_root(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    health_parser = subparsers.add_parser("health", help="Print service metadata.")
    _add_repo_root(health_parser)

    tools_parser = subparsers.add_parser("tools", help="List registered tools.")
    _add_repo_root(tools_parser)

    server_parser = subparsers.add_parser("server", help="Run the local HTTP API.")
    _add_repo_root(server_parser)
    server_parser.add_argument("--host", default=DEFAULT_API_HOST)
    server_parser.add_argument("--port", type=int, default=DEFAULT_API_PORT)

    codex_parser = subparsers.add_parser(
        "codex-router",
        help="Control or inspect codex-router.",
    )
    _add_repo_root(codex_parser)
    codex_subparsers = codex_parser.add_subparsers(
        dest="codex_command",
        required=True,
    )

    codex_status = codex_subparsers.add_parser("status", help="Show status JSON.")
    codex_status.add_argument("--port", type=int, default=DEFAULT_CODEX_ROUTER_PORT)

    codex_start = codex_subparsers.add_parser("start", help="Start codex-router.")
    codex_start.add_argument("--port", type=int, default=DEFAULT_CODEX_ROUTER_PORT)
    codex_start.add_argument("--host")
    codex_start.add_argument("--public", action="store_true")
    codex_start.add_argument("--no-wait", action="store_true")
    codex_start.add_argument("--timeout", type=int, default=90)

    codex_stop = codex_subparsers.add_parser("stop", help="Stop codex-router.")
    codex_stop.add_argument("--process-id", type=int)
    codex_stop.add_argument("--timeout", type=int, default=30)

    markitdown_parser = subparsers.add_parser(
        "markitdown",
        help="Run markitdown-backed actions.",
    )
    _add_repo_root(markitdown_parser)
    markitdown_subparsers = markitdown_parser.add_subparsers(
        dest="markitdown_command",
        required=True,
    )

    convert_parser = markitdown_subparsers.add_parser(
        "convert",
        help="Convert a local file to Markdown.",
    )
    convert_parser.add_argument("input_path")
    convert_parser.add_argument("-o", "--output")
    convert_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON even when no output path is provided.",
    )
    convert_parser.add_argument(
        "--no-markdown",
        action="store_true",
        help="Omit markdown from JSON output.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = getattr(args, "repo_root", None)

    try:
        if args.command == "health":
            from . import __version__
            from .paths import find_repo_root

            _print_json(
                {
                    "ok": True,
                    "service": "bwtools-api",
                    "version": __version__,
                    "repo_root": str(find_repo_root(repo_root)),
                }
            )
            return 0

        if args.command == "tools":
            _print_json(tool_inventory(repo_root))
            return 0

        if args.command == "server":
            run_server(args.host, args.port, repo_root)
            return 0

        if args.command == "codex-router":
            if args.codex_command == "status":
                _print_json(codex_router_status(repo_root, args.port))
                return 0
            if args.codex_command == "start":
                result = codex_router_start(
                    repo_root,
                    public=args.public,
                    host=args.host,
                    port=args.port,
                    no_wait=args.no_wait,
                    timeout=args.timeout,
                )
                _print_json(result)
                return 0 if result.get("ok") else 1
            if args.codex_command == "stop":
                result = codex_router_stop(
                    repo_root,
                    process_id=args.process_id,
                    timeout=args.timeout,
                )
                _print_json(result)
                return 0 if result.get("ok") else 1

        if args.command == "markitdown" and args.markitdown_command == "convert":
            result = convert_markitdown(
                args.input_path,
                args.output,
                include_markdown=not args.no_markdown,
                repo_root=repo_root,
            )
            if args.output or args.json or args.no_markdown:
                _print_json({"ok": True, **result})
            else:
                sys.stdout.write(result["markdown"])
            return 0

    except Exception as exc:  # noqa: BLE001 - CLI should surface actionable text
        _print_json({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        return 1

    parser.error("Unhandled command")
    return 2
