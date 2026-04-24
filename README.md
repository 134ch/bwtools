# bwtools

A git-tracked collection of developer tools, each in its own folder.

The direction is to make `bwtools` the stable local surface that other
projects and agents call when they need common tools. Callers should not need
to hard-code every upstream repository's layout, install notes, ports, or
quirks. Each tool folder records the upstream source and exposes the
bwtools-specific usage contract around it.

Today this repo has a first thin front door in `bwtools-api/`: a local CLI and
HTTP API that exposes tool inventory, codex-router controls, and markitdown
conversion. New tools should plug into that surface instead of teaching every
caller about their upstream-specific commands.

## Installing

The default repo-level Python install is:

```powershell
python -m pip install -r requirements.txt
```

That installs the current Python-backed tool runtimes from vendored local
source paths and installs the first-party `bwtools` CLI. If you only need one
tool, use that tool's own
`requirements.txt` instead:

```powershell
cd bwtools-api
python -m pip install -r requirements.txt

cd ../codex-router
python -m pip install -r requirements.txt

cd ../markitdown
python -m pip install -r requirements.txt
```

`codex-router` requires Python 3.13 or newer. `bwtools-api` and `markitdown`
support Python 3.10 or newer.

## API Surface

`bwtools-api/` provides the current local service and CLI. Other projects and
agents can call this surface instead of knowing every upstream command, port, or
file layout.

Start the API:

```powershell
bwtools server
```

Default bind: `http://127.0.0.1:2480`.

Current endpoints:

- `GET /health`
- `GET /tools`
- `GET /tools/{name}`
- `GET /tools/codex-router/status`
- `POST /tools/codex-router/start`
- `POST /tools/codex-router/stop`
- `POST /tools/markitdown/convert`

Useful CLI equivalents:

```powershell
bwtools tools
bwtools codex-router status
bwtools markitdown convert .\input.pdf --output .\output.md
```

## Convention

Vendored third-party tools live in their own top-level folder and follow this
layout:

```text
<tool-name>/
|-- README.md       # What it is, how we use it, how it differs from upstream
|-- LICENSE         # Preserved upstream license (required by most OSS licenses)
|-- UPSTREAM.txt    # Source URL, version, commit SHA, vendor date
`-- upstream/       # Verbatim upstream tree (with .git/ removed)
```

Any bwtools-specific additions (wrappers, sidecars, configs) live alongside
`upstream/` but **never inside it**. This keeps the upstream diff empty and
makes resyncing to a newer upstream release mechanical.

First-party bwtools code, such as `bwtools-api/`, has `README.md`, `LICENSE`,
`UPSTREAM.txt`, and its own install file, but no vendored `upstream/` tree.

## Current tools

| Tool           | Upstream                                           | Status          | Purpose                                          |
|----------------|----------------------------------------------------|-----------------|--------------------------------------------------|
| bwtools-api    | first-party                                        | active          | Local CLI/HTTP front door over the repo tools |
| codex-router   | [Soju06/codex-lb](https://github.com/Soju06/codex-lb)     | vendored        | Multi-account ChatGPT/Codex device-auth load balancer; Vertex fallback is postponed |
| markitdown     | [microsoft/markitdown](https://github.com/microsoft/markitdown) | vendored        | Convert PDF/DOCX/PPTX/etc. to Markdown for LLM pipelines |
| yt-transcripts | *TBD*                                              | **stub - planned** | Bulk YouTube transcript extractor: URL list in, one Markdown per video out |

See each tool's own `README.md` for details.

## Status

This is a git repository at `github.com/134ch/bwtools`. It is meant to be
referenced from other projects and by local agents as the canonical place for
these tools on this machine.
