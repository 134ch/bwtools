# bwkit

A local, curated tool gateway for AI agents.

One registry, many harnesses. Attach `bwkit` once and every agent you use —
Claude Code, Codex, opencode, Cline, Continue, Hermes — can call the same
curated set of local tools, with uniform metrics and BYOK credentials.

Design principles:

- **Curated, not exhaustive.** Useful + maintained in, unmaintained out.
- **Local by default.** Your machine is the compute. Secrets never leave it.
- **BYOK.** bwkit only eases setup; you own the keys and accounts.
- **Tool N+1 doesn't touch tools 1..N.** Add to the catalog, write one adapter, done.

Status: **Phase 1** — CLI + Python + MCP stdio + one tool (`markitdown`).
Phase 2 (HTTP API + dashboard) and Phase 3 (LangChain/LlamaIndex adapters,
markitdown extensions) will layer on top without changing Phase 1 contracts.

## Install

```bash
pip install -e ".[markitdown]"
```

Requires Python ≥ 3.10.

## Quickstart

```bash
bwkit list                             # see catalog + enabled state
bwkit doctor                           # check extras + env vars

# Invoke directly
bwkit call markitdown --arg source=./README.md

# Pipe output
bwkit call markitdown --arg source=https://example.com -o page.json

# Metrics (local SQLite at ~/.bwkit/bwkit.db)
bwkit metrics summary --since 24h
bwkit metrics recent  --limit 20
bwkit metrics errors  --since 7d
```

## Wire into agents (MCP)

`bwkit` speaks MCP over stdio. Any harness that supports MCP can call its tools.

### Claude Code

Add to `~/.claude/mcp.json` (Windows: `%USERPROFILE%\.claude\mcp.json`):

```jsonc
{
  "mcpServers": {
    "bwkit": {
      "command": "bwkit",
      "args": ["mcp"]
    }
  }
}
```

### Codex / opencode / Cline / Continue

Each harness has its own MCP config file but the entry shape is identical
— `command: "bwkit"`, `args: ["mcp"]`. See each harness's docs.

## Bring your own keys (BYOK)

Tools that need credentials read them from:

1. Your process environment.
2. `~/.bwkit/.env` (overlay, used when a var isn't already in the env).

```ini
# ~/.bwkit/.env
# (markitdown v1 needs no keys)
```

Never commit this file. `bwkit doctor` prints which declared vars are set.

## Curation

The catalog lives at `src/bwkit/catalog.yaml`. Adding a tool means:

1. Append one row to `catalog.yaml`.
2. Create `src/bwkit/tools/<name>.py`, exporting a `SPEC: ToolSpec` constant.
3. Keep heavy imports **inside** `run()` — module import must succeed without extras.
4. Declare any `extras` and `env_vars` in `SPEC`.
5. Add `tests/test_<name>.py`.

Removing a tool: delete its row + its adapter file. Existing user overrides
for that tool are warned about, not errored.

## Metrics

Metrics are per-user (single-user local database, no shared server):

- Stored at `~/.bwkit/bwkit.db` (SQLite).
- **No raw inputs or outputs** — only `input_hash` for retry grouping.
- Columns: `ts, tool, caller, transport, latency_ms, status, error_code, error_class, input_hash`.
- `error_code` is a **stable machine-readable** string (e.g. `missing_extra`,
  `missing_credential`, `tool_disabled`, `invalid_arguments`, `conversion_failed`).
  Agents can branch on this for retry logic.

## Layout

```
src/bwkit/
  catalog.yaml          # curated list (package-owned)
  core/                 # registry, runner, metrics, creds, errors, spec
  tools/                # one module per curated tool
  transports/           # mcp_stdio (Phase 1), http_api (Phase 2) …
  cli.py                # `bwkit` entrypoint
```

## Roadmap

- **Phase 2** — HTTP API (`bwkit serve`) + localhost dashboard, OpenAI-
  function-calling translator.
- **Phase 3** — LangChain / LlamaIndex adapter factories, markitdown
  extensions (YouTube, audio transcription, Azure DocIntel, LLM captions) as
  separate tool entries with their own extras.

## License

MIT.
