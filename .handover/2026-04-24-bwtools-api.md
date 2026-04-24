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
- Added codex-router prerequisite docs for Bun:
  - `README.md` now notes that codex-router's upstream frontend expects
    Bun 1.3.7+ and that the current bwtools dashboard wrapper uses Node.js/npm.
  - `codex-router/README.md` now has a prerequisites section covering
    Python 3.13+, `uv`, Bun 1.3.7+, and Node.js/npm.
  - `codex-router/requirements.txt` now documents non-pip prerequisites.
- Added `bwagent-support/` as a first-party bwtools support suite for the
  `134ch/bwagent-ops` agent workspace:
  - `README.md` records that these are bwtools support capabilities, not tools
    owned by the `bwagent-ops` repo.
  - `LICENSE`, `UPSTREAM.txt`, and `requirements.txt` establish the first-party
    tool folder shape.
  - The planned build order is `bwtools bwagent doctor`, knowledge ingestion,
    daily brief builder, prospect packet builder, friction review, Hermes skill
    sync, and content/approval ledger.
- Implemented the first read-only support command:
  - Added `bwtools-api/src/bwtools_api/bwagent.py`.
  - Added CLI route `bwtools bwagent doctor`.
  - Added HTTP route `GET /tools/bwagent-support/doctor`.
  - The doctor discovers the sibling `bwagent-ops` checkout or
    `BWAGENT_OPS_ROOT`, reads current Hermes facts from
    `ops/HERMES-SETUP.md`, checks key local files, reads target repo git status
    with a per-command `safe.directory`, and optionally probes the documented
    WebUI health endpoint.
- Updated root `README.md`, `bwtools-api/README.md`, and
  `bwtools-api/src/bwtools_api/tools.py` so `bwagent-support` is listed as
  `partial`, with `bwtools bwagent doctor` active and the remaining support
  commands still planned.

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
- `Get-Content codex-router\upstream\frontend\package.json` to confirm
  upstream declares `packageManager: "bun@1.3.7"`.
- `python -m bwtools_api bwagent doctor --skip-webui` from
  `bwtools-api\src`; returned ok with one warning because
  `C:\_Development\bwagent-ops` has untracked `.claude/`.
- `python -m bwtools_api bwagent doctor --webui-timeout 1` from
  `bwtools-api\src`; returned ok with warnings for untracked `.claude/` and a
  sandbox socket-permission failure probing
  `http://100.101.10.44:8787/health`.
- Temporary in-process API probe on port `2482` for
  `GET /tools/bwagent-support/doctor?skip_webui=true`, then stopped the test
  server.

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
- **Documented Bun without editing upstream.** codex-lb's upstream frontend
  declares Bun in `frontend/package.json`, but bwtools keeps this correction in
  wrapper docs and requirements comments so `upstream/` remains untouched.
- **Renamed the planned support surface to `bwagent-support`.** The user
  clarified that these are not `bwagent-ops` tools; `bwtools` is the support
  repo for the `bwagent-ops` agent. The name and command namespace now reflect
  bwtools ownership.
- **Exposed support commands as `bwtools bwagent ...`.** This avoids implying
  that the commands are installed from or owned by the `bwagent-ops` repo while
  still making their target agent workspace obvious.
- **Created a support suite folder instead of only a roadmap file.** This makes
  the future support set visible to the normal bwtools inventory and gives
  future implementations a clear home.
- **Implemented `bwtools bwagent doctor` first.** Runtime truth, VM/WebUI state,
  and model routing have caused confusion, so read-only verification should
  come before more automation.
- **Kept the first doctor local/read-only.** It reads docs and local git status
  and only probes the documented WebUI health URL. It does not SSH or mutate the
  VM because credential and network assumptions should be explicit later.

## Open questions blocking the next session

- Should `bwtools-api` be kept as a short-lived local process that agents start
  on demand, or should it get Windows service/task helpers later?
- Should `bwtools-api` expose mutating endpoints such as codex-router start/stop
  beyond localhost? For now, it binds localhost only.
- Should the next tool be `yt-transcripts`, or should we add a formal tool
  registration spec first so outside agents can propose tools consistently?
- Should markitdown conversion return Markdown inline by default for API calls,
  or should large-file calls require an `output_path` and omit inline Markdown?
- Should `codex-router/bin/build-dashboard.ps1` be changed to prefer Bun when
  it is installed, falling back to npm only if Bun is unavailable?
- Should future support commands remain under `bwtools bwagent ...`, or should
  `bwtools` also expose shorter aliases after the surface stabilizes?
- Should `bwtools bwagent doctor` SSH into the VM next, or first accept pasted
  VM command output to avoid credential and network dependencies?
- Should the doctor treat a dirty `bwagent-ops` workspace as warn forever, or
  fail when files outside allowed local caches are dirty?

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
7. Install Bun 1.3.7+ on fresh machines before using upstream codex-lb frontend
   commands. Keep Node.js/npm available until the bwtools dashboard wrapper is
   changed.
8. Run `bwtools bwagent doctor` from a normal shell after installing from the
   repo root and confirm the console script works outside `bwtools-api\src`.
9. Decide whether untracked `C:\_Development\bwagent-ops\.claude\` is expected.
   The doctor currently reports it as a warning from target repo git status.
10. Extend `bwtools bwagent doctor` with either pasted VM output parsing or SSH
    checks for:
    - `systemctl status hermes-webui --no-pager`
    - `curl http://100.101.10.44:8787/health`
    - `hermes model`
    - VM-side `git status --short --branch`
    - `tailscale status`

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
- Bun is not a Python dependency and cannot be installed by
  `codex-router/requirements.txt`; it is documented there as a system
  prerequisite only.
- The current bwtools dashboard wrapper still requires Node.js/npm. Installing
  Bun alone is not enough for that wrapper until the script is changed.
- Do not implement auto-sending outreach in `bwagent-support`. All
  prospect-facing output still requires Bach approval.
- Do not revive the old custom Hermes UI by default; `bwagent-ops` says the
  active path is upstream Hermes WebUI.
- The first doctor uses `git -c safe.directory=...` for
  `C:\_Development\bwagent-ops` because the sandbox user otherwise hits Git's
  dubious-ownership guard.
- The WebUI health probe may report a Windows socket permission error
  (`WinError 10013`) inside this sandbox. Treat that as an environment warning
  unless the same command fails from a normal user shell.
