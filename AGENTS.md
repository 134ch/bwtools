# Agent conventions for bwtools

This file is read by AI coding agents working in this repo (Claude Code,
Codex, Hermes, Cline, etc.). Follow these rules.

## Handover-before-push rule

**Before every `git push` from any agent session, the agent MUST write a
handover document.**

Location: `.handover/YYYY-MM-DD[-slug].md`
(ISO date, optional slug if multiple handovers land the same day.)

The handover and the rest of the session's changes are committed and pushed
**together** in the same push. No exceptions. If the session ends without
a handover, the push is incomplete.

### What the handover must contain

1. **What was built / changed this session** — concrete files touched,
   commands run, decisions that produced code.
2. **Decisions made + rationale** — especially the ones that future-you
   (or a different agent) won't be able to reconstruct from the diff.
   Include alternatives that were considered and rejected, with why.
3. **Open questions blocking the next session** — what the user still has
   to decide, what we don't know yet, what's waiting on external facts.
4. **Concrete next steps** — an ordered checklist a future agent can pick
   up cold and execute. Name specific files, not vague intents.
5. **Risks / traps** — constraints a future agent might stumble over
   (hard-coded ports, version requirements, case-insensitive-FS quirks,
   licenses, credentials).

### Why

Sessions are short and context windows are smaller than the problems. The
diff tells you *what* changed, not *why* or *what's next*. Every agent
starting cold needs the handover to avoid either (a) redoing work or
(b) contradicting past decisions. The push-together rule guarantees the
handover and the code it describes never drift apart.

## Other conventions

- Each tool lives in its own top-level folder with `README.md`,
  `LICENSE`, `UPSTREAM.txt`, and `upstream/` (verbatim vendor). See the
  top-level `README.md` for the full layout rule.
- **Never modify files under any tool's `upstream/`.** Keep our divergence
  in sibling folders (e.g. `codex-router/sidecar/`) so resyncing to a newer
  upstream stays mechanical.
- On Windows, the filesystem is case-insensitive. Don't create a file and
  a directory with the same name at the same level (that's why provenance
  files are `UPSTREAM.txt`, not `UPSTREAM`).
- Don't make the repo a git monorepo subtree of upstream sources. We
  vendor by copying the tree minus `.git/`, recording the SHA in
  `UPSTREAM.txt`. That's the only supported model right now.
