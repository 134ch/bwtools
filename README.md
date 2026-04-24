# bwtools

A git-tracked collection of developer tools, each in its own folder.

The direction is to make `bwtools` the stable local surface that other
projects and agents call when they need common tools. Callers should not need
to hard-code every upstream repository's layout, install notes, ports, or
quirks. Each tool folder records the upstream source and exposes the
bwtools-specific usage contract around it.

Today this repo is still mostly a vendored-tool registry. Over time, wrappers,
launchers, configs, and small adapters can be added beside each upstream tree
to make the tools easier to call consistently.

## Installing

The default repo-level Python install is:

```powershell
python -m pip install -r requirements.txt
```

That installs the current Python-backed tool runtimes from vendored local
source paths. If you only need one tool, use that tool's own
`requirements.txt` instead:

```powershell
cd codex-router
python -m pip install -r requirements.txt

cd ../markitdown
python -m pip install -r requirements.txt
```

`codex-router` requires Python 3.13 or newer. `markitdown` supports Python
3.10 or newer.

## Future API Surface

The likely end state is a small local `bwtools` API service that exposes a
stable interface over these tools. Other projects and agents would call the
`bwtools` API instead of knowing every upstream command, port, or file layout.

The first useful API should stay thin:

- health and tool inventory endpoints
- launch/status helpers for long-running tools such as `codex-router`
- document conversion endpoints backed by `markitdown`
- transcript extraction endpoints once `yt-transcripts` is implemented

When that service exists, it should live in its own top-level folder with its
own `requirements.txt`; the current root `requirements.txt` is only the
aggregate runtime install for existing tools.

## Convention

Every tool lives in its own top-level folder and follows the same layout:

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

## Current tools

| Tool           | Upstream                                           | Status          | Purpose                                          |
|----------------|----------------------------------------------------|-----------------|--------------------------------------------------|
| codex-router   | [Soju06/codex-lb](https://github.com/Soju06/codex-lb)     | vendored        | Multi-account ChatGPT/Codex device-auth load balancer; Vertex fallback is postponed |
| markitdown     | [microsoft/markitdown](https://github.com/microsoft/markitdown) | vendored        | Convert PDF/DOCX/PPTX/etc. to Markdown for LLM pipelines |
| yt-transcripts | *TBD*                                              | **stub - planned** | Bulk YouTube transcript extractor: URL list in, one Markdown per video out |

See each tool's own `README.md` for details.

## Status

This is a git repository at `github.com/134ch/bwtools`. It is meant to be
referenced from other projects and by local agents as the canonical place for
these tools on this machine.
