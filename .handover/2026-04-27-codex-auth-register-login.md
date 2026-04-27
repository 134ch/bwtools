# 2026-04-27 codex-auth-register-login

## What was built / changed this session

- Added a maintained tool folder at `codex-auth-register-login/` around the prototype snapshot in `codex-auth-register-login/upstream/`.
- Extended `codex-auth-register-login/account_registrar.py` with:
  - `native-playwright` mode that launches a fresh installed Chrome session per account and attaches over CDP.
  - `run-mode` support for `register-and-auth` and `device-auth-only`.
  - file-bridge support for OTP and device-code prompts via `.bridge/request.json` and `.bridge/response.json`.
  - direct OpenAI Codex device-auth flow support via `--codex-device-url`.
  - onboarding automation for full name, age, Engineering role, and Skip.
  - Codex consent-page handling.
  - device-code prompt handling.
  - safer navigation/title handling after login-step transitions.
- Added `codex-auth-register-login/bridge_reply.py` to answer a pending bridge request from a second terminal.
- Added and updated regression coverage in `codex-auth-register-login/tests/test_account_registrar.py`.
- Updated `codex-auth-register-login/README.md` to describe the real live modes we used.
- Tightened `codex-auth-register-login/.gitignore` to avoid committing live CSV credentials and runtime artifacts such as `.bridge/`, logs, and local config dirs.
- Removed `444alvin` from `codex-auth-register-login/input-codex.csv` locally because the user said that workspace was full. This file is intentionally ignored and is not part of the commit.

## Commands run

- Local test and validation commands:
  - `python -m pytest .\tests\test_account_registrar.py`
  - `python -c "from pathlib import Path; import ast; ast.parse(Path('account_registrar.py').read_text(encoding='utf-8')); print('syntax ok')"`
- Repeated live runs with:
  - `python .\account_registrar.py .\input-codex.csv --flow-mode native-playwright --run-mode register-and-auth ...`
  - `python .\account_registrar.py .\input-codex.csv --flow-mode native-playwright --run-mode device-auth-only ...`
  - `python .\bridge_reply.py --bridge-dir .\.bridge --value <OTP_OR_DEVICE_CODE>`

## Decisions made + rationale

- Chose `native-playwright` as the primary live mode because Playwright-launched Chromium repeatedly hit Cloudflare/login instability on this Windows machine, while a fresh installed Chrome session attached over CDP worked materially better.
- Added a strict split between `register-and-auth` and `device-auth-only` because already-registered accounts such as `456salah` needed to bypass the invite/onboarding path entirely.
- Used a file bridge instead of interactive stdin prompts because the workflow repeatedly needed the operator to paste OTPs/device codes asynchronously while the browser stayed open.
- Kept the tool out of the main bwtools workflow for now. The live batch was workable under supervision, but the completion/status reporting is not reliable enough for general integration yet.
- Updated `.gitignore` to exclude `input-codex.csv` and runtime artifacts because the live CSV contains real credentials and must never be pushed.

## Live results observed this session

- Accounts the user confirmed as done:
  - `456salah` finished manually earlier and was then treated as device-auth only.
  - `111alvin` reached Codex signed-in state.
  - `333alvin` was manually completed after registration plus device-auth page.
  - `cey111` was manually completed after registration plus device-auth page.
  - `cey222` had OTP and device code bridged; user confirmed it was done.
  - `cey333` had OTP bridged; user later said it was done.
- Account with unresolved automation quality:
  - `222alvin` repeatedly re-requested the same device code on the callback page. The user moved on instead of finishing a clean scripted completion.

## Open questions blocking the next session

- The tool still does not produce a trustworthy final success signal for Codex device-auth completion. Some runs clearly succeeded in the browser but the runner either timed out or reported success too early.
- There may still be edge cases where a manual OTP/device-code submission in the browser must be mirrored into the bridge to unblock the Python process. The UX is not yet explicit about this.
- We do not yet have clean test fixtures for the repeated device-code retry page seen with `222alvin`.

## Concrete next steps

1. Refactor `codex-auth-register-login/account_registrar.py` so each run/account uses a unique temp bridge directory and unique log/report file instead of shared `bridge-run.err.log`, `bridge-run.out.log`, and `.bridge/request.json`.
2. Add startup and shutdown cleanup in `codex-auth-register-login/account_registrar.py` so stale Python/browser sessions cannot keep writing into new runs.
3. Add explicit persistence for completed/skipped accounts, for example `codex-auth-register-login/account_state.json`, so manually finished accounts are not reprocessed.
4. Add regression tests in `codex-auth-register-login/tests/test_account_registrar.py` for:
   - Codex consent page
   - device-code entry page
   - signed-in success page
   - repeated device-code callback retry
5. Tighten success detection in `codex-auth-register-login/account_registrar.py` so completion is only marked on real signed-in markers, not just the callback URL.
6. Only after the above, reconsider whether the tool should be integrated into the wider bwtools workflow.

## Risks / traps

- `codex-auth-register-login/input-codex.csv` contains live credentials. It is intentionally ignored and must stay out of commits.
- Runtime files under `codex-auth-register-login/.bridge/` and local logs contain OTP/device-code traces and must also stay uncommitted.
- The current shared bridge/log design allows one stale process to contaminate later runs. This happened repeatedly in the session and is the main operational trap.
- Windows filesystem behavior and handle locking caused intermittent failures when deleting or replacing `.bridge/request.json`.
- The mock tests passed syntax and static validation, but full live confidence still depends on future hardening; the tool is not ready to be promoted into the main workflow yet.
