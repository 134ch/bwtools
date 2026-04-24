# Handover - 2026-04-24 codex-router wrappers

Session owner: Codex. Working directory: `C:\_Development\bwtools`.

## What was built / changed this session

- Clarified the top-level `README.md` direction: `bwtools` is intended to be
  the stable local tool surface that other projects and agents call, rather
  than every caller hard-coding each upstream tool.
- Added install convenience files:
  - `requirements.txt`
  - `codex-router/requirements.txt`
  - `markitdown/requirements.txt`
  - `markitdown/requirements-all.txt`
  - `yt-transcripts/requirements.txt`
- Updated tool READMEs:
  - `codex-router/README.md` now documents bwtools wrapper scripts,
    dashboard build, `-Public` bind mode, install options, and the local smoke
    result.
  - `codex-router/sidecar/README.md` now says Vertex fallback is postponed.
  - `markitdown/README.md` now points at local requirements files.
  - `yt-transcripts/README.md` now includes the empty requirements convention.
- Added bwtools-owned codex-router scripts under `codex-router/bin/`:
  - `build-dashboard.ps1` / `build-dashboard.cmd`
  - `start.ps1` / `start.cmd`
  - `status.ps1` / `status.cmd`
  - `stop.ps1` / `stop.cmd`
- Installed user-level `pip` and `uv` on this machine to support the native
  codex-lb path. `uv` resolved to
  `C:\Users\Bach\AppData\Roaming\Python\Python314\Scripts\uv.exe`.
- Ran `uv sync` / `uv sync --frozen` in `codex-router/upstream`, creating the
  ignored `.venv/`.
- Built frontend dashboard assets with `npm.cmd exec vite build`, producing
  ignored files under `codex-router/upstream/app/static/`.
- Updated the local user Codex config outside the repo:
  `C:\Users\Bach\.codex\config.toml` now contains
  `openai_base_url = "http://127.0.0.1:2455/backend-api/codex"`.
  Backup:
  `C:\Users\Bach\.codex\config.toml.bak-2026-04-24-bwtools-router`.

Commands run during verification:

- `uv sync`
- `uv sync --frozen`
- supervised `uv run codex-lb --host 127.0.0.1 --port 2455`
- `npm.cmd install --no-package-lock`
- `npm.cmd exec vite build`
- `python -m pip install --dry-run --no-deps -r ...` for root and per-tool
  requirements files
- `codex-router\bin\status.cmd`
- PowerShell parse checks for every `codex-router/bin/*.ps1`
- `git diff --check`
- `git status -- ':/**/upstream/**'`

## Decisions made + rationale

- **Postponed Vertex fallback.** The user wants Codex device auth as the main
  path. Keeping Vertex out of the critical path lets the repo become useful
  faster.
- **Added wrapper scripts beside `upstream/`, not inside it.** This preserves
  the vendored upstream tree and follows `AGENTS.md`.
- **Added `.cmd` launchers for Windows.** This machine blocks some `.ps1`
  shims due to execution policy. The `.cmd` files invoke PowerShell with
  `-ExecutionPolicy Bypass` and make the scripts easier for future agents.
- **Used `uv run --frozen` in the wrapper.** Plain `uv run` rewrote
  `codex-router/upstream/uv.lock` because upstream's lockfile reports
  `codex-lb` as `1.13.1` while `pyproject.toml` says `1.14.1`. The wrapper
  should avoid mutating vendored upstream files.
- **Used `npm.cmd exec vite build` instead of `npm run build`.** The upstream
  `npm run build` fails TypeScript checking in
  `frontend/src/components/donut-chart.tsx` on a Recharts type issue, but Vite
  successfully emits the dashboard assets.
- **Root requirements are aggregate; per-tool requirements are local.** This
  keeps one-command install possible while still letting agents install only
  the tool they need.

## Open questions blocking the next session

- Should we import `C:\Users\Bach\.codex\auth.json` into codex-lb to avoid a
  new browser login? This contains live auth tokens and needs explicit user
  approval.
- Is Tailscale exposure being handled by another agent on port `2455` or
  `2555`? codex-lb's default service port is `2455`. If `2555` is desired,
  it needs an explicit bind or port forward.
- Should the future `bwtools` API service be built next, or should the next
  concrete tool be `yt-transcripts`?
- Should generated dashboard assets be committed later for zero-build
  dashboard startup, or should they remain ignored and built locally?

## Concrete next steps

1. From `codex-router/`, run `bin\build-dashboard.cmd` on fresh machines
   before opening the dashboard.
2. Start codex-router locally with `bin\start.cmd`; use `bin\start.cmd -Public`
   only when tailnet/LAN access is intentionally desired.
3. Open `http://127.0.0.1:2455` and add/import at least one Codex account.
4. If importing existing Codex credentials, use the dashboard import flow or
   API with `C:\Users\Bach\.codex\auth.json` only after user approval.
5. Verify a future Codex session can use
   `http://127.0.0.1:2455/backend-api/codex` after an account exists.
6. Decide whether the next repo feature is a thin `bwtools` API service or the
   first implementation of `yt-transcripts`.

## Risks / traps

- `codex-lb` is not currently running. It was stopped before an interrupted
  attempt to restart on `0.0.0.0`.
- This machine's observed Tailscale IP was `100.118.40.92`, not
  `100.101.10.44`.
- `codex-router/upstream/uv.lock` is inconsistent with upstream
  `pyproject.toml`; avoid unfrozen `uv run` / `uv sync` unless intentionally
  refreshing upstream.
- `npm run build` currently fails on an upstream TypeScript/Recharts type
  mismatch. Use `bin\build-dashboard.cmd` or `npm.cmd exec vite build`.
- Runtime data is ignored under `codex-router/codex-lb-data/`. It contains DB,
  logs, encryption key, and PID state; do not commit it.
- `codex-router/upstream/app/static/`, `frontend/node_modules/`, `.venv/`, and
  `__pycache__/` are generated/ignored local artifacts.
- The root `AGENTS.md` forbids modifying files under any `upstream/` tree.
