# bwtools

> Handling and installing tools across a dozen AI agents is exhausting.
> I wanted this to feel like writing **one command**.

A local, curated compilation of tools any AI agent can attach to.
Start it with `bwkit mcp`. Plug it into Claude Code, Codex, opencode, Cline,
Continue, a Hermes-based agent — whatever harness you run. They all get the
same tools, the same BYOK credentials, and the same per-user metrics.

One registry. One install. Many agents.

---

## Why this exists

I was building **bwghostwriting-os**, and inside it, **bwagent-os** — my
Hermes-based agent stack. Every few days I'd wire up another harness for
another workflow: Claude Code for heavy edits, opencode for quick shell
tasks, a Hermes agent for long-running jobs.

Each one needed its own tool plumbing.

Each one had its own config format, its own way of passing credentials, its
own idea of what a "tool" even was. I was copy-pasting the same PDF-to-Markdown
wrapper into three agents. Rotating an API key meant editing four files. A
tool that worked in Claude Code silently didn't exist in my Hermes agent
because I hadn't ported it yet.

I wanted to stop doing that. I wanted **one place** where every good tool
lives, curated and maintained, that every agent on my machine could talk to.

So: `bwtools`. One registry. BYOK. Local only. MCP as the lingua franca.
Metrics so I can see which of my agents are actually using which tools and
which ones keep failing. Easy enough to add a new tool that I actually will,
instead of putting it off for another week.

This is that compilation.

---

## What's in the box

| Tool | What it does | Status |
|------|--------------|--------|
| [`markitdown`](https://github.com/microsoft/markitdown) | Convert PDF / DOCX / PPTX / XLSX / HTML / text files and HTTP(S) URLs to Markdown | ✅ Phase 1 |

The catalog grows. The rule is **curated, not exhaustive**: useful +
maintained in, unmaintained out. Less reliable tools > many unreliable ones.

**Planned next**: to be curated from lists like
[awesome-opensource-ai](https://github.com/alvinreal/awesome-opensource-ai)
and [Awesome-LLMOps](https://github.com/tensorchord/Awesome-LLMOps), one tool
at a time, each with its own minimal adapter.

---

## Setup

```bash
git clone https://github.com/134ch/bwtools.git
cd bwtools/bwkit
pip install -e ".[markitdown]"
```

Requires Python ≥ 3.10.

Verify:

```bash
bwkit list                 # see the catalog
bwkit doctor               # check extras + declared env vars
```

---

## How to call tools

Three ways, same tool, same result, same metrics row.

### 1. From the CLI

```bash
bwkit call markitdown --arg source=./report.pdf
bwkit call markitdown --arg source=https://example.com
bwkit call markitdown --arg source=./slides.pptx -o out.json
```

Result is JSON on stdout:

```json
{"ok": true, "result": {"title": "Report Q4", "text": "# Report Q4\n\n..."}}
```

Errors are JSON too, with a **stable machine-readable `error_code`**
(`missing_extra`, `source_not_found`, `unsupported_scheme`, …) so agents can
branch on it:

```json
{"ok": false, "error_code": "source_not_found", "message": "..."}
```

### 2. From an AI agent (MCP)

`bwkit mcp` speaks the Model Context Protocol over stdio. Any harness that
supports MCP can attach.

**Claude Code** — `~/.claude/mcp.json` (Windows: `%USERPROFILE%\.claude\mcp.json`):

```json
{
  "mcpServers": {
    "bwkit": {
      "command": "bwkit",
      "args": ["mcp"]
    }
  }
}
```

**Codex / opencode / Cline / Continue / your own Hermes agent** — same shape,
different config file. See each harness's MCP docs.

Once attached, every enabled tool in `catalog.yaml` shows up in that agent's
tool list, with auto-generated JSON Schemas.

### 3. From Python

```python
from bwkit.tools.markitdown import convert

result = convert("report.pdf")         # or a URL
print(result["title"], result["text"][:200])
```

The Python surface is a convenience layer. The stable contracts are the CLI
flags and MCP tool schemas.

---

## Bring your own keys (BYOK)

bwtools only eases setup. **You own the accounts, you own the keys.**

Tools that need credentials read them from:

1. Your process environment.
2. `~/.bwkit/.env` as an overlay (used only when a variable isn't already in
   the environment).

```ini
# ~/.bwkit/.env — create this file yourself, never commit it.
# OPENAI_API_KEY=sk-...
# AZURE_DOCINTEL_KEY=...
```

`bwkit doctor` prints which declared vars are set, so you know exactly what's
missing before a tool call fails.

markitdown itself needs **no keys** for the Phase 1 feature set (local files,
HTML, plain HTTP). Future LLM/Azure/YouTube extensions will declare their own.

---

## Metrics

Every call goes through one choke point, so every call gets recorded:

- Stored locally at `~/.bwkit/bwkit.db` (SQLite, per-user by construction).
- **No raw inputs or outputs** — only an `input_hash` for retry grouping.
- Stable `error_code` strings agents can branch on.

Inspect:

```bash
bwkit metrics summary --since 24h
bwkit metrics recent  --limit 20 --tool markitdown
bwkit metrics errors  --since 7d
```

Each row shows which **caller** (Claude Code / Codex / CLI / …) and which
**transport** (MCP / CLI) produced it — so when a call fails, you can see
whether it's a transport issue or a tool issue without guessing.

---

## Adding a tool to the catalog

Four steps, one tool at a time, zero impact on existing tools:

1. Append a row to `bwkit/src/bwkit/catalog.yaml`:

   ```yaml
   - name: yourtool
     module: bwkit.tools.yourtool
     summary: One line describing what it does.
     upstream: https://github.com/...
     maintained: true
     default_enabled: true
     extras: [yourtool]
     env_vars: [YOURTOOL_API_KEY]   # or []
   ```

2. Create `bwkit/src/bwkit/tools/yourtool.py` exporting `SPEC: ToolSpec`.
   Keep heavy imports **inside** `run()` — module import must succeed
   without extras installed.

3. Declare the extra in `bwkit/pyproject.toml` under `[project.optional-dependencies]`.

4. Add `bwkit/tests/test_yourtool.py`.

Removing a tool is symmetrical: delete its row and its adapter. Existing user
overrides for the removed tool produce a **warning, not an error.**

---

## Roadmap

- **Phase 1 (shipped)** — Catalog + registry + runner + metrics + BYOK + CLI + MCP stdio + markitdown.
- **Phase 2** — HTTP API (`bwkit serve`) + localhost dashboard, OpenAI-function-calling translator.
- **Phase 3** — LangChain / LlamaIndex adapter factories. markitdown extensions (YouTube, audio transcription, Azure Document Intelligence, LLM image captioning) as separate curated tool entries.

More tools get curated in as they prove useful and maintained.

---

## Repo layout

```
bwtools/
└── bwkit/                # the gateway package
    ├── pyproject.toml
    ├── README.md         # package-level docs
    ├── src/bwkit/
    │   ├── catalog.yaml
    │   ├── core/         # registry, runner, metrics, creds, errors, spec
    │   ├── tools/        # one module per curated tool
    │   ├── transports/   # mcp_stdio (Phase 1), http_api (Phase 2) …
    │   └── cli.py
    └── tests/
```

The `bwkit/` subfolder is the first — and currently only — package in this
compilation. Future sibling packages (e.g. bigger tool families that earn
their own namespace) can live next to it.

---

## License

MIT.
