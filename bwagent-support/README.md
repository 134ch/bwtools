# bwagent-support

**Status: partial.** `bwtools bwagent doctor` is implemented through
`bwtools-api`; the remaining support commands are planned.

Future first-party bwtools support capabilities for the BWGhostwriting/Hermes
agent workspace: `134ch/bwagent-ops`.

These are not `bwagent-ops` tools. They belong in `bwtools` because this repo
is the reusable local tool surface that supports the `bwagent-ops` agent. The
`bwagent-ops` repo should remain focused on operating the business, prompts,
runbooks, skills, and knowledge.

## Principle

Build tools only when they reduce repeated operating friction.

Do not add automation just because it is interesting. The tool should make the
daily Hermes/BWGhostwriting workflow clearer, safer, or faster.

## Recommended Build Order

### 1. `bwtools bwagent doctor`

Verify the live Hermes operating stack before a session starts.

Checks:

- Hermes WebUI health at the current Tailscale URL
- `hermes-webui.service` status on the VM
- current `hermes model` provider/model
- repo sync state on laptop and VM
- GitHub auth readiness on the VM
- Tailscale/DNS health
- optional codex-lb route status when that path is active

Why first:

- Runtime truth has already caused confusion.
- A doctor command prevents agents from debugging stale assumptions.
- It should be read-only by default.

Current minimum version:

1. Read current runtime assumptions from `bwagent-ops/ops/HERMES-SETUP.md`.
2. Check local repo status.
3. Show expected VM/Tailscale/WebUI facts.
4. Probe the documented WebUI health URL when reachable.
5. Print a JSON pass/warn/fail report.

Later version:

1. Optionally accept pasted command output from the VM.
2. SSH into the VM.
3. Run WebUI, systemd, Hermes, Git, Tailscale, and DNS checks directly.
4. Emit stable machine-readable JSON for future agents.

### 2. Knowledge Ingestion Tool

Turn raw materials into correctly placed knowledge-system inputs.

Inputs:

- PDFs
- DOCX
- Markdown
- notes
- exported transcripts
- URLs
- YouTube transcripts

Outputs:

- files under `bwagent-ops/knowledge/raw/`
- rows in `bwagent-ops/knowledge/INGESTION-MANIFEST.csv`
- optional draft wiki update plan, but not automatic wiki edits by default

Integration:

- call `bwtools` markitdown for document conversion
- call `bwtools` yt-transcripts when implemented

### 3. Daily Brief Builder

Produce one clean operating brief from the live workspace state and daily
inputs.

Reads:

- `bwagent-ops/prompts/daily-operator-prompt.md`
- core config under `bwagent-ops/context/config/`
- recent signals, learnings, friction, and optional daily notes

Outputs:

- today's business priority
- content priority
- outreach priority
- manual checklist
- blockers and missing inputs
- friction worth logging if repeated

### 4. Prospect Packet Builder

Prepare high-quality prospect research packets before Hermes drafts outreach.

Inputs:

- LinkedIn/profile URL
- website URL
- pasted public text
- Bach notes

Outputs:

- ICP score
- qualification rationale
- specific personalization hook
- recommended channel
- risks or reasons to discard
- draft inputs for LinkedIn DM or cold email

Constraints:

- research/prep only
- no sending
- no bypassing Bach approval

### 5. Friction Logger And Weekly Review

Make friction capture and review consistent.

Commands:

- append structured friction to `bwagent-ops/ops/FRICTION-BACKLOG.md`
- summarize repeated friction weekly
- recommend whether an item should become a workflow change, skill, or tool

### 6. Hermes Skill Sync

Keep repo skills and live Hermes skills aligned.

Checks:

- compare `bwagent-ops/hermes-skills/` with `~/.hermes/skills/` on the VM
- detect missing or stale skills
- show what would change before syncing

Optional action:

- sync selected skills to the live Hermes home after confirmation

### 7. Content And Approval Ledger

Track what drafts were produced, approved, revised, published, and what
happened after publishing.

Possible storage:

- start with SQLite or CSV under `bwagent-ops/data/`
- avoid reviving the legacy custom UI unless explicitly needed

## What Not To Build Yet

- Auto-sending outreach.
- Full CRM automation before prospect packets work manually.
- A new custom UI to replace upstream Hermes WebUI.
- Client-delivery automation inside `bwagent-ops`.
- Permanent strategy changes based on one bad output.

## Relationship To bwagent-ops

`bwtools` should provide reusable tooling:

- document conversion
- transcript extraction
- local API/CLI access
- codex-router/codex-lb access
- Hermes/BWGhostwriting agent support utilities

`bwagent-ops` should keep the business-specific operating layer:

- prompts
- runbooks
- skills
- knowledge
- daily operating records

When possible, `bwagent-support` should call existing `bwtools` capabilities
instead of duplicating generic tooling.
