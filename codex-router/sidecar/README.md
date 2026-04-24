# codex-router sidecar (design stub)

**Status:** postponed design only. No code in this folder yet.

The current development path is to use Codex / ChatGPT device-auth accounts
through upstream codex-lb first. Vertex fallback should be revisited only after
the core router workflow is proven useful locally.

## Goal

A thin reverse proxy that sits **in front of** codex-lb and transparently
falls back to Google Vertex AI when every pooled ChatGPT account is
quota-exhausted.

```
         ┌──────────────────────┐
clients ─┤  sidecar :2456       │──► codex-lb :2455 ──► ChatGPT accounts
  │      │  - forwards 99% of   │         │
  │      │    traffic unchanged │         │ 429 / insufficient_quota
  │      │  - translates + fa-  │◄────────┘
  │      │    lls back on 429   │
  │      └──────────────────────┘
  │                │
  │                └──► Vertex AI (fallback)
  │
  └── Hermes / Codex CLI / Claude Code / OpenCode
      (point base_url at the sidecar, not codex-lb)
```

## Why a sidecar, not a fork of codex-lb

codex-lb has **no provider abstraction**. Its upstream URL is hard-coded in
`.env.example` to `https://chatgpt.com/backend-api`, and its OAuth client ID
is specific to ChatGPT. Adding Vertex as a first-class provider would touch
a large fraction of its codebase and create a permanent merge burden when
upstream releases new versions.

A sidecar is a few hundred lines, keeps upstream pristine, and can be
rewritten without touching codex-lb.

## Scope v1

- Codex primary, single Vertex project fallback
- Non-streaming completions only
- Triggers fallback on:
  - HTTP 429 with `insufficient_quota`
  - HTTP 503 from codex-lb indicating all accounts exhausted
- Logs every fallback event for observability

## Out of scope v1

- Streaming (SSE)
- Multi-Vertex-account pooling
- Anthropic as a third provider
- Dashboard integration with codex-lb (Vertex requests will not appear on
  codex-lb's dashboard)
- OAuth for Vertex (API key + project ID only)

## Translation responsibilities

When falling back, the sidecar must map the OpenAI-style payload that the
client sent to Vertex's `generateContent` format, and map the Vertex
response back.

| OpenAI field          | Vertex equivalent                         |
|-----------------------|-------------------------------------------|
| `messages[]`          | `contents[]`                              |
| `role: "user"`        | `role: "user"`                            |
| `role: "assistant"`   | `role: "model"`                           |
| `role: "system"`      | `systemInstruction`                       |
| `content` (string)    | `parts: [{ text }]`                       |
| `max_tokens`          | `generationConfig.maxOutputTokens`        |
| `temperature`         | `generationConfig.temperature`            |

Model mapping will be config-driven (e.g., `gpt-4o-mini` → `gemini-2.5-flash`).

## Tech choice

**Python + FastAPI + httpx**, to match codex-lb's stack and share a single
`uv` environment. Node/Express was considered and rejected to avoid a
dual-runtime install.

## Config shape (planned)

`sidecar/config.yaml`:

```yaml
upstream:
  codex_lb_url: "http://127.0.0.1:2455"

fallback:
  enabled: true
  provider: vertex
  vertex:
    project_id: "your-gcp-project"
    location: "us-central1"
    api_key_env: "GOOGLE_AI_API_KEY"
  model_map:
    gpt-4o-mini: gemini-2.5-flash
    gpt-4o:      gemini-2.5-pro

listen:
  host: "127.0.0.1"
  port: 2456
```

## Verification (once built)

1. Start codex-lb with zero registered accounts (forces 401/503).
2. Start the sidecar on 2456 with Vertex configured.
3. `curl -X POST http://127.0.0.1:2456/v1/chat/completions ...` — should succeed
   via Vertex fallback.
4. Register a Codex account, repeat — should succeed via Codex (no fallback).
5. Inspect sidecar logs for a fallback-event line when expected.

## Open questions (to resolve before implementing)

- Which GCP project + API key to use (needs user decision at build time).
- Which OpenAI ↔ Gemini model mapping makes sense for the user's workload.
- Whether to use Vertex AI API keys or Application Default Credentials.
