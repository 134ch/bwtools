"""`bwkit` CLI entrypoint (Phase 1).

Commands
--------
list                          — catalog with enabled/disabled state
doctor                        — check extras + env vars for enabled tools
enable <tool> / disable <tool>  — write ~/.bwkit/config.toml
call <tool> --arg k=v ...     — run a tool; prints JSON result (or -o FILE)
mcp                           — stdio MCP server
metrics summary | recent | errors
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Optional

import typer

from bwkit.core import config as config_mod
from bwkit.core import creds as creds_mod
from bwkit.core.errors import BwkitError
from bwkit.core.metrics import Metrics, iso_since
from bwkit.core.registry import load_registry
from bwkit.core.runner import Runner


app = typer.Typer(add_completion=False, no_args_is_help=True, help="bwkit — local tool gateway.")
metrics_app = typer.Typer(no_args_is_help=True, help="Query local metrics.")
app.add_typer(metrics_app, name="metrics")


def _load() -> tuple[dict, Metrics, Runner]:
    registry = load_registry(config=config_mod.load())
    metrics = Metrics()
    runner = Runner(registry=registry, metrics=metrics)
    return registry, metrics, runner


# ---------------------------------------------------------------- list

@app.command("list")
def list_cmd() -> None:
    """Show the curated catalog and each tool's enabled state."""
    registry, _, _ = _load()
    if not registry:
        typer.echo("(catalog is empty)")
        return
    width = max(len(name) for name in registry)
    for name in sorted(registry):
        r = registry[name]
        state = "enabled " if r.enabled else "disabled"
        tag = "" if r.spec.maintained else " [UNMAINTAINED]"
        typer.echo(f"{name.ljust(width)}  {state}  {r.spec.summary}{tag}")


# ---------------------------------------------------------------- doctor

@app.command()
def doctor() -> None:
    """Check each enabled tool: extras importable? declared env vars set?"""
    registry, _, _ = _load()
    ok = True
    for name in sorted(registry):
        resolved = registry[name]
        if not resolved.enabled:
            continue
        typer.echo(f"[{name}]")
        # Importability is implicit (module already imported by load_registry).
        # Probe heavy extras by re-importing the adapter's declared extras' top package.
        for extra in resolved.spec.extras:
            installed = _extra_installed(extra)
            mark = "OK  " if installed else "MISS"
            if not installed:
                ok = False
            typer.echo(f"  extra {extra:15s} {mark}"
                       + ("" if installed else f"   (install: pip install 'bwkit[{extra}]')"))
        status = creds_mod.declared_status(resolved.spec.env_vars)
        for var, present in status.items():
            mark = "OK  " if present else "MISS"
            typer.echo(f"  env   {var:15s} {mark}")
        if not resolved.spec.extras and not resolved.spec.env_vars:
            typer.echo("  (no extras / env vars declared)")
    if not ok:
        raise typer.Exit(code=1)


def _extra_installed(extra: str) -> bool:
    """Heuristic: the 'markitdown' extra installs the 'markitdown' package, etc."""
    try:
        importlib.import_module(extra.replace("-", "_"))
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------- enable / disable

@app.command()
def enable(tool: str) -> None:
    """Enable a tool (writes ~/.bwkit/config.toml)."""
    config_mod.set_enabled(tool, True)
    typer.echo(f"enabled: {tool}")


@app.command()
def disable(tool: str) -> None:
    """Disable a tool (writes ~/.bwkit/config.toml)."""
    config_mod.set_enabled(tool, False)
    typer.echo(f"disabled: {tool}")


# ---------------------------------------------------------------- call

@app.command()
def call(
    tool: str = typer.Argument(..., help="Tool name as listed by `bwkit list`."),
    arg: list[str] = typer.Option(
        [], "--arg", "-a",
        help="Pass an argument as key=value. Repeat --arg for multiple.",
    ),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="Write result to FILE instead of stdout."),
) -> None:
    """Invoke a tool and print its JSON result."""
    arguments = _parse_kv(arg)
    _, _, runner = _load()
    try:
        result = runner.call(tool, caller="cli", transport="cli", arguments=arguments)
    except BwkitError as e:
        typer.echo(json.dumps({"ok": False, "error_code": e.code, "message": str(e)}), err=True)
        raise typer.Exit(code=_exit_code_for(e.code))

    payload = json.dumps({"ok": True, "result": result}, default=str)
    if output:
        output.write_text(payload, encoding="utf-8")
    else:
        typer.echo(payload)


def _parse_kv(items: list[str]) -> dict:
    out: dict = {}
    for item in items:
        if "=" not in item:
            raise typer.BadParameter(f"expected key=value, got: {item!r}")
        k, v = item.split("=", 1)
        out[k.strip()] = _coerce(v)
    return out


def _coerce(v: str):
    # Conservative coercion: JSON first (handles numbers, booleans, null, arrays, objects),
    # fall back to the raw string.
    try:
        return json.loads(v)
    except json.JSONDecodeError:
        return v


def _exit_code_for(error_code: str) -> int:
    return {
        "missing_extra": 2,
        "missing_credential": 2,
        "invalid_arguments": 2,
        "tool_disabled": 3,
        "unknown_tool": 3,
    }.get(error_code, 1)


# ---------------------------------------------------------------- mcp

@app.command()
def mcp() -> None:
    """Run the stdio MCP server. Wire into your agent's mcp.json."""
    from bwkit.transports.mcp_stdio import serve
    serve()


# ---------------------------------------------------------------- metrics

@metrics_app.command("summary")
def metrics_summary(
    since: Optional[str] = typer.Option(None, help="e.g. 24h, 7d, 30m"),
    tool: Optional[str] = typer.Option(None),
) -> None:
    m = Metrics()
    since_iso = iso_since(since) if since else None
    typer.echo(json.dumps(m.summary(since=since_iso, tool=tool), default=str))


@metrics_app.command("recent")
def metrics_recent(
    limit: int = typer.Option(50),
    tool: Optional[str] = typer.Option(None),
) -> None:
    m = Metrics()
    typer.echo(json.dumps(m.recent(limit=limit, tool=tool), default=str))


@metrics_app.command("errors")
def metrics_errors(
    since: Optional[str] = typer.Option(None, help="e.g. 24h, 7d"),
) -> None:
    m = Metrics()
    since_iso = iso_since(since) if since else None
    typer.echo(json.dumps(m.errors(since=since_iso), default=str))


# ---------------------------------------------------------------- entry

def main() -> None:
    try:
        app()
    except BwkitError as e:
        typer.echo(f"bwkit error [{e.code}]: {e}", err=True)
        sys.exit(_exit_code_for(e.code))


if __name__ == "__main__":
    main()
