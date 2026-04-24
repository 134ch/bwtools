# bwtools-api

First-party local API and CLI surface for `bwtools`.

The goal is to give agents and projects one stable thing to call instead of
hard-coding each vendored tool's paths, ports, command names, and setup quirks.

## Install

From this folder:

```powershell
python -m pip install -r requirements.txt
```

From the repo root, the aggregate install also includes this package:

```powershell
python -m pip install -r requirements.txt
```

The API package itself has no runtime dependency outside the Python standard
library. Tool actions still depend on the underlying tool being installed and
ready. For example, `markitdown` conversion needs the vendored markitdown
package dependencies installed.

## CLI

List registered tools:

```powershell
bwtools tools
```

Check the codex-router service that powers Codex device-auth routing:

```powershell
bwtools codex-router status
```

Start or stop codex-router through the existing bwtools wrapper scripts:

```powershell
bwtools codex-router start
bwtools codex-router start --public
bwtools codex-router stop
```

Convert a file through markitdown:

```powershell
bwtools markitdown convert .\document.pdf --output .\document.md
```

## HTTP API

Start the local API service:

```powershell
bwtools server
```

Default bind: `127.0.0.1:2480`.

Current endpoints:

| Method | Path                              | Purpose                                |
|--------|-----------------------------------|----------------------------------------|
| GET    | `/health`                         | Service health and repo root           |
| GET    | `/tools`                          | Tool inventory                         |
| GET    | `/tools/{name}`                   | One registered tool                    |
| GET    | `/tools/codex-router/status`      | codex-router PID and health probe      |
| POST   | `/tools/codex-router/start`       | Start codex-router wrapper             |
| POST   | `/tools/codex-router/stop`        | Stop codex-router wrapper              |
| POST   | `/tools/markitdown/convert`       | Convert a local file to Markdown       |

Example markitdown request:

```powershell
$body = @{
  input_path = "C:\path\to\document.pdf"
  output_path = "C:\path\to\document.md"
  include_markdown = $false
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:2480/tools/markitdown/convert `
  -Body $body `
  -ContentType application/json
```

Example codex-router start body:

```json
{
  "public": false,
  "port": 2455
}
```

Use `"public": true` only when exposing codex-router on a trusted LAN or
tailnet.

## Repo Root Discovery

When installed editable from this checkout, `bwtools` can usually find the repo
root automatically. If a caller runs it from another directory and discovery
fails, set:

```powershell
$env:BWTOOLS_ROOT = "C:\_Development\bwtools"
```

## Upstream

This folder is first-party. `UPSTREAM.txt` records that there is no external
upstream tree to preserve.
