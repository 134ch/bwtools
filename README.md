# bwtools

A collection of vendored third-party developer tools, each in its own folder.

## Convention

Every tool lives in its own top-level folder and follows the same layout:

```
<tool-name>/
├── README.md       # What it is, how we use it, how it differs from upstream
├── LICENSE         # Preserved upstream license (required by most OSS licenses)
├── UPSTREAM.txt    # Source URL, version, commit SHA, vendor date
└── upstream/       # Verbatim upstream tree (with .git/ removed)
```

Any bwtools-specific additions (wrappers, sidecars, configs) live alongside
`upstream/` but **never inside it**. This keeps the upstream diff empty and
makes resyncing to a newer upstream release mechanical.

## Current tools

| Tool           | Upstream                                           | Status          | Purpose                                          |
|----------------|----------------------------------------------------|-----------------|--------------------------------------------------|
| codex-router   | [Soju06/codex-lb](https://github.com/Soju06/codex-lb)     | vendored        | Multi-account ChatGPT/Codex load balancer + planned Vertex AI fallback sidecar |
| markitdown     | [microsoft/markitdown](https://github.com/microsoft/markitdown) | vendored        | Convert PDF/DOCX/PPTX/etc. to Markdown for LLM pipelines |
| yt-transcripts | *TBD*                                              | **stub — planned** | Bulk YouTube transcript extractor: URL list in, one Markdown per video out |

See each tool's own `README.md` for details.

## Status

This directory is not currently a git repository. It's a local collection of
sources meant to be referenced from other projects on this machine.
