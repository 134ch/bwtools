# 2026-04-30 abandonment note

## What was built / changed this session

- Reviewed the latest handover, `.handover/2026-04-27-codex-auth-register-login.md`.
- Confirmed `origin/main` was already up to date.
- Decided to stop active work on this repository instead of spending another
  session hardening `codex-auth-register-login`.
- Added this abandonment handover so future agents do not restart the same work
  without understanding why it was paused.

No production code was changed in this session.

## Current worktree state

At the time this handover was written, the worktree still had pre-existing
uncommitted or untracked files:

```text
 M codex-router/upstream/uv.lock
?? bwroute/
?? codex-router/HANDOVER.md
?? codex-router/upstream/frontend/package-lock.json
?? ztemp/
```

These were intentionally left untouched. In particular, the files under
`codex-router/upstream/` conflict with the repository convention that vendored
upstream trees should stay verbatim.

## Decisions made + rationale

- Do not continue hardening `codex-auth-register-login` right now.
  - The next proper pass would likely take more than one hour.
  - Browser/device-code/OTP flows are externally fragile and require live
    manual validation.
  - The last handover identified core reliability gaps: shared bridge files,
    stale processes, weak success detection, and missing state persistence.
- Do not commit generated or dirty upstream files.
  - The repo layout depends on keeping `upstream/` directories mechanically
    resyncable.
  - Committing npm lockfiles or uv lock changes inside `codex-router/upstream/`
    would preserve drift from the upstream snapshot.
- Preserve context instead of cleaning aggressively.
  - Some untracked directories may contain user experiments or runtime output.
    They should be reviewed manually before removal.

## Open questions blocking any future restart

- Is `bwtools` still useful as a local stable tool surface, or should it be
  archived entirely?
- Should `codex-router` be kept, resynced from upstream, or removed from this
  repo?
- Is `bwroute/` an intentional new tool, a temporary prototype, or disposable
  generated output?
- Should `codex-auth-register-login` be archived as an experimental tool, or
  deleted because it touches live credentials and brittle auth flows?

## Concrete next steps if someone resumes

1. Run `git status --short --branch` from the repo root and confirm the dirty
   files still match this handover.
2. Review `bwroute/` and decide whether it should become a proper top-level
   tool folder with `README.md`, `LICENSE`, `UPSTREAM.txt`, and `upstream/`, or
   whether it should be removed/ignored.
3. Review `ztemp/` for any useful notes, then remove or ignore it if it is only
   scratch output.
4. Decide what to do with `codex-router/HANDOVER.md`. If it contains useful
   project history, move the relevant content into `.handover/`; otherwise
   remove it.
5. Resolve `codex-router/upstream/uv.lock` and
   `codex-router/upstream/frontend/package-lock.json` without preserving
   accidental upstream drift. Prefer resyncing `codex-router/upstream/` from a
   known upstream commit instead of hand-editing vendored files.
6. If abandoning permanently, update the top-level `README.md` with an archive
   notice and push a final commit.

## Risks / traps

- `codex-auth-register-login/input-codex.csv` is intentionally ignored and may
  contain live credentials. Do not add it to git.
- Runtime bridge/log files from `codex-auth-register-login` may contain OTP or
  device-code traces. Treat them as sensitive.
- `codex-auth-register-login` should not be considered reliable automation.
  It needs per-run bridge isolation, cleanup, state persistence, stronger
  success detection, and tests before reuse.
- Do not modify files under any tool's `upstream/` directory unless the
  explicit task is to replace the vendored upstream snapshot and update
  provenance.
