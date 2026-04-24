# markitdown

A vendored copy of [microsoft/markitdown](https://github.com/microsoft/markitdown)
main (commit `a51f725`, package version `0.1.6b2`).

## What is markitdown?

A Python utility that converts almost any file format into Markdown, primarily
for feeding documents into LLM pipelines. Supported inputs include:

- Office: DOCX, PPTX, XLSX, XLS
- PDF
- Images (with OCR via optional plugin)
- Audio (transcription)
- HTML
- CSV / JSON / XML
- ZIP archives (walks contents)
- EPUB
- URLs (YouTube transcripts, Wikipedia, Bing SERP, etc.)

It exposes both a Python library (`from markitdown import MarkItDown`) and a
CLI (`markitdown path/to/file.pdf > out.md`).

## What's in this folder

| Path           | What                                       |
|----------------|--------------------------------------------|
| `upstream/`    | Verbatim markitdown source tree. Do not edit. |
| `LICENSE`      | Upstream MIT license                       |
| `UPSTREAM.txt` | Source provenance and refresh instructions |

The upstream is a monorepo. Packages of interest:

- `upstream/packages/markitdown/` - core library + CLI
- `upstream/packages/markitdown-mcp/` - MCP server wrapper
- `upstream/packages/markitdown-ocr/` - optional OCR plugin

## How this differs from upstream

No modifications yet - this is a pure verbatim vendor. When we start using
markitdown from other projects, any custom wrappers or configs will live
alongside `upstream/`, not inside it.

## Install & Use

Core package:

```bash
python -m pip install -r requirements.txt
```

All optional upstream dependencies:

```bash
python -m pip install -r requirements-all.txt
```

Then:

```bash
markitdown path/to/file.pdf > out.md
```

Or through the repo-level `bwtools` CLI:

```bash
bwtools markitdown convert path/to/file.pdf --output out.md
```

From Python:

```python
from markitdown import MarkItDown

md = MarkItDown()
print(md.convert("some/file.pdf").text_content)
```

## Version note

Upstream `main` at vendor time is a beta (`0.1.6b2`). The last tagged stable
release was `0.1.5` (2026-02-20). If stability matters more than recency,
re-vendor from the `v0.1.5` tag - see `UPSTREAM.txt` for the refresh steps.

## License

MIT, Copyright (c) Microsoft Corporation (see `LICENSE`).
