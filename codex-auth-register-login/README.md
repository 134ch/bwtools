# codex-auth-register-login

Local interactive automation for this workflow:

1. You prepare invite links plus email/password pairs.
2. The tool opens a fresh browser session per account.
3. It uses a fresh native Chrome session per account and attaches Playwright
   over CDP for the live flow.
4. If OTP or device code appears, it can pause on a file bridge so an operator
   can answer from another terminal or manually finish the browser step.
5. After registration, it can continue into direct OpenAI Codex device auth
   using the same logged-in browser session.
6. It repeats for the next account.

## What is in this folder

| Path | What |
|------|------|
| `upstream/` | Verbatim local prototype snapshot from `ztemp/automated-codex-auth-register-login`. Do not edit. |
| `account_registrar.py` | Maintained local runner for registration plus optional Codex device auth. |
| `selectors.json` | Default selectors and URL heuristics. Adjust this when target pages change. |
| `accounts_sample.csv` | Sample pipe-delimited input file. |
| `bridge_reply.py` | Sends an OTP or device-code response into a pending bridge request. |
| `tests/` | Local mock-based regression tests. |

## Why this exists

The original prototype had the right overall intent but was not reliable
enough to run:

- proxy settings were not isolated per account
- the documented no-proxy fallback was not implemented
- OTP waiting was too weak
- there was no support for the follow-up Codex device auth step
- there were no automated tests

The maintained version fixes those issues and keeps the prototype snapshot for
reference.

## Install

From this folder:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Local run

Register plus device auth with the current native-browser path:

```powershell
python .\account_registrar.py .\accounts_sample.csv `
  --flow-mode native-playwright `
  --run-mode register-and-auth `
  --bridge-dir .\.bridge
```

Device-auth only for accounts that already finished registration:

```powershell
python .\account_registrar.py .\accounts_sample.csv `
  --flow-mode native-playwright `
  --run-mode device-auth-only `
  --bridge-dir .\.bridge
```

Useful flags:

```powershell
python .\account_registrar.py .\accounts.csv `
  --flow-mode native-playwright `
  --run-mode register-and-auth `
  --start-at 1 `
  --limit 1 `
  --bridge-dir .\.bridge `
  --bridge-timeout-seconds 1800 `
  --device-auth-timeout-seconds 300 `
  --account-timeout-seconds 900 `
  --otp-wait-seconds 180 `
  --report .\out\registration_report.json `
  --log .\out\registration.log
```

Bridge reply from a second terminal:

```powershell
python .\bridge_reply.py --bridge-dir .\.bridge --value 123456
```

## Input file

Pipe-delimited columns:

```text
invite_link|email|password|proxy
https://example.com/register?code=abc123|user1@example.com|Pass123|
https://example.com/register?code=def456|user2@example.com|Pass456|http://user:pass@127.0.0.1:8080
```

Rules:

- header row is optional
- `proxy` may be blank
- one browser session is created per account

## Testing

The tests do not hit external services. They spin up a local mock registration
site and a mock device-auth flow:

```powershell
python -m pytest .\tests\test_account_registrar.py
```

## Notes

- Visible browser mode is the default because OTP usually needs manual entry.
- `native-playwright` is the recommended live mode on this machine.
- `register-and-auth` is for new accounts; `device-auth-only` is for accounts
  that already completed registration.
- The direct device-auth page defaults to `https://auth.openai.com/codex/device`
  and can be overridden with `--codex-device-url`.
- One brand-new browser process is launched for each account.
- The same per-account browser context is reused for registration and device
  auth so the newly registered session can continue into the OAuth flow.
- A plain file bridge is used for OTP and device-code prompts when
  `--bridge-dir` is set.
- This is still a staging tool. It worked with supervision, but it needs more
  hardening before being promoted into a broader bwtools workflow.
- `--start-at` and `--limit` are intended for single-account local debugging
  before running the full CSV.
