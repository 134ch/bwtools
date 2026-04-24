# Handover - 2026-04-24 bwtools-api

Session owner: Codex. Working directory: `C:\_Development\bwtools`.

## What was built / changed this session

- Added `bwtools-api/` as first-party bwtools code:
  - `pyproject.toml` exposes console scripts `bwtools` and `bwtools-api`.
  - `requirements.txt` installs the package editable from its folder.
  - `README.md`, `LICENSE`, and `UPSTREAM.txt` document that it is first-party
    and has no external upstream tree.
  - `src/bwtools_api/paths.py` discovers the repo root from `BWTOOLS_ROOT`, the
    current working directory, or the editable source path.
  - `src/bwtools_api/tools.py` contains the tool registry, codex-router
    status/start/stop helpers, and markitdown conversion helper.
  - `src/bwtools_api/server.py` provides a standard-library HTTP API.
  - `src/bwtools_api/cli.py` provides the matching CLI surface.
- Updated the root `requirements.txt` to include `-e ./bwtools-api` before the
  existing vendored local packages.
- Updated `README.md` to describe `bwtools-api` as the current front door, list
  API endpoints, and clarify the distinction between vendored third-party tools
  and first-party bwtools code.
- Updated `codex-router/README.md` with `bwtools codex-router ...` commands.
- Updated `markitdown/README.md` with `bwtools markitdown convert ...`.

Commands run during verification:

- `git pull --ff-only origin main`
- `python -m compileall -q bwtools-api\src`
- `python -m bwtools_api health` with `PYTHONPATH` pointed at
  `bwtools-api\src`
- `python -m bwtools_api tools` with `PYTHONPATH` pointed at
  `bwtools-api\src`
- `python -m bwtools_api codex-router status` with `PYTHONPATH` pointed at
  `bwtools-api\src`
- Temporary API probe on port `2481`:
  `python -m bwtools_api server --port 2481`, then `GET /health`, then stopped
  the process.
- `python -m pip install --dry-run --no-deps -r requirements.txt` from
  `bwtools-api/`
- `python -m pip install --dry-run --no-deps -r requirements.txt` from the repo
  root
- `git diff --check`
- `git status --short -- ':/**/upstream/**'`

## Decisions made + rationale

- **Used only the Python standard library for the API server.** This keeps the
  first API layer small and avoids introducing FastAPI/uvicorn until we need
  middleware, OpenAPI docs, auth, or async workloads.
- **Made `bwtools-api` first-party instead of pretending it has a vendored
  upstream.** It has `README.md`, `LICENSE`, `UPSTREAM.txt`, and install files,
  but no `upstream/` tree because there is no external source to preserve.
- **Default API bind is `127.0.0.1:2480`.** This avoids colliding with
  codex-lb on `2455` and keeps the API local by default.
- **Kept codex-router control as wrappers over `codex-router/bin/*.ps1`.** The
  existing wrappers already encode local runtime paths and `uv --frozen`; the
  new API should not duplicate that process-launch logic.
- **Added markitdown as the first real callable tool surface.** It is the
  lowest-friction useful tool because it does not require account login.
- **Added `BWTOOLS_ROOT` fallback.** Editable installs discover the checkout,
  but console scripts launched from arbitrary directories may need an explicit
  repo root.

## Open questions blocking the next session

- Should `bwtools-api` be kept as a short-lived local process that agents start
  on demand, or should it get Windows service/task helpers later?
- Should `bwtools-api` expose mutating endpoints such as codex-router start/stop
  beyond localhost? For now, it binds localhost only.
- Should the next tool be `yt-transcripts`, or should we add a formal tool
  registration spec first so outside agents can propose tools consistently?
- Should markitdown conversion return Markdown inline by default for API calls,
  or should large-file calls require an `output_path` and omit inline Markdown?

## Concrete next steps

1. Install from the repo root:
   `python -m pip install -r requirements.txt`.
2. Run `bwtools tools` and confirm the console script resolves from a normal
   shell.
3. Start the API with `bwtools server`, then call:
   `GET http://127.0.0.1:2480/health`.
4. Try the first real tool call:
   `bwtools markitdown convert <input-file> --output <output.md>`.
5. If adding `yt-transcripts`, add it through `bwtools-api/src/bwtools_api/tools.py`
   and update `bwtools-api/README.md`, root `README.md`, and
   `yt-transcripts/README.md`.
6. If another agent proposes a tool, ask it for a spec matching the bwtools
   registry fields before integrating code.

## Risks / traps

- Do not modify any `upstream/` files. This session did not touch upstream
  trees.
- `codex-router status` reported no wrapper PID file and a timeout probing
  `http://127.0.0.1:2455/health/live` from this process, even though the user
  confirmed the active Codex session is using codex-lb on port `2455`. Treat the
  new status helper as a local checkout probe, not proof that every tailnet or
  externally launched router path is down.
- `bwtools-api` is editable-installed in root `requirements.txt`; a non-editable
  install may not know the checkout path unless `BWTOOLS_ROOT` is set.
- `bwtools-api` can read local files and start/stop local services. Keep it
  bound to `127.0.0.1` unless a later session deliberately adds auth and ACLs.
- `python -m compileall` and pip dry-runs created ignored local artifacts
  (`__pycache__/` and `*.egg-info/`). They should remain untracked.
- Windows line-ending warnings appeared during `git diff --check`; no whitespace
  errors were reported.
