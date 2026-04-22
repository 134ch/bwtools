# codex-router

A vendored copy of [Soju06/codex-lb](https://github.com/Soju06/codex-lb) v1.14.1
plus a (planned) Vertex AI fallback sidecar.

## What is codex-lb?

codex-lb is a load balancer / reverse proxy for ChatGPT accounts. You register
multiple Codex (ChatGPT) device-code OAuth logins, and codex-lb pools them
behind a single endpoint, distributes requests across accounts, tracks usage,
and surfaces everything in a dashboard.

Clients that can be pointed at it include anything that speaks the OpenAI
chat-completions API or the Codex CLI backend API:

- Hermes WebUI
- Codex CLI
- Claude Code (when using an OpenAI-compatible endpoint)
- OpenCode
- Any app with a configurable `base_url`

## What's in this folder

| Path         | What                                                                 |
|--------------|----------------------------------------------------------------------|
| `upstream/`  | Verbatim codex-lb v1.14.1 source (commit `637fa85`). Do not edit.    |
| `sidecar/`   | Planned Vertex AI fallback proxy. **Design stub only — no code yet.** |
| `LICENSE`    | Upstream MIT license (required redistribution notice)                |
| `UPSTREAM.txt` | Source provenance and refresh instructions                         |

## How this differs from upstream

- Upstream is vendored verbatim. No file under `upstream/` is modified.
- All bwtools-specific divergence will live under `sidecar/`.
- `sidecar/` is currently a design stub — see `sidecar/README.md` for the plan.

## Running the load balancer (upstream only)

### Option A — native Python with `uv` (Windows)

Requires **Python 3.13+** (upstream's `pyproject.toml` pins `requires-python = ">=3.13"`).

```bash
cd upstream
uv sync
uv run codex-lb
```

Dashboard + API: <http://127.0.0.1:2455>
OAuth callback port: 1455 (hard-coded upstream — do not change)

### Option B — Docker

```bash
docker run -d --name codex-lb \
  -p 2455:2455 \
  -p 1455:1455 \
  -v codex-lb-data:/var/lib/codex-lb \
  ghcr.io/soju06/codex-lb:latest
```

### Option C — `docker-compose` (from vendored compose files)

```bash
cd upstream
docker compose up -d
```

## Adding accounts

Visit <http://127.0.0.1:2455>, log in (first run prompts for a dashboard
password), and click "Add Account". Each account walks through ChatGPT's
device-code OAuth flow.

## Pointing clients at it

| Client        | Endpoint                                              |
|---------------|-------------------------------------------------------|
| OpenAI-style  | `http://127.0.0.1:2455/v1`                            |
| Codex CLI     | `http://127.0.0.1:2455/backend-api/codex`             |
| Transcription | `http://127.0.0.1:2455/backend-api/transcribe`        |

## Known constraints (from upstream)

- **Port 1455 cannot be changed.** Upstream's `.env.example` warns:
  *"Do not change the port. OpenAI dislikes changes."* This is the redirect
  URI registered with ChatGPT's OAuth client. If another service on your
  machine uses 1455, stop it before starting codex-lb.
- **Python 3.13 hard requirement** for native installs. Use Docker on older
  Pythons.
- **ChatGPT/Codex accounts only.** No upstream support for Vertex, Anthropic,
  or any other provider. The Vertex fallback is our addition (see `sidecar/`).
- **No documented quota-exhaustion failover between accounts.** Upstream
  distributes load; if every pooled account hits a 429, the request fails.

## License

- Upstream: MIT, Copyright (c) 2025 Soju06 (see `LICENSE`)
- Our additions (sidecar, when written): MIT
