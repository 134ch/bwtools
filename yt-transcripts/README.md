# yt-transcripts

**Status: stub. Not yet implemented.**

Planned tool: a bulk YouTube transcript extractor.

## Goal

Feed it a list of YouTube URLs, get back one Markdown file per video ready
to drop into an LLM pipeline or a markitdown-converted document set.

## Planned I/O contract

**Input:** a text file with one YouTube URL per line (or stdin).

**Output:** a directory of `<videoId>.md` files. Each file has YAML
frontmatter and the transcript as the body:

```markdown
---
url: https://www.youtube.com/watch?v=dQw4w9WgXcQ
video_id: dQw4w9WgXcQ
title: "Rick Astley - Never Gonna Give You Up (Official Music Video)"
channel: "Rick Astley"
published: 2009-10-25
duration_seconds: 213
language: en
source: auto-generated        # or "manual"
extracted_at: 2026-04-23T12:00:00Z
---

[transcript body, one line per subtitle cue or one paragraph per speaker
turn — decision deferred to build time]
```

This output shape is deliberately aligned with how `../markitdown/` emits
files, so downstream tooling can consume both interchangeably.

## Open decisions (to resolve at build time)

1. **Extraction backend.** Candidates:
   - [`jdepoix/youtube-transcript-api`](https://github.com/jdepoix/youtube-transcript-api)
     — pure Python, MIT, lightweight. Works for most public videos.
     No audio download, no ffmpeg.
   - [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) — much heavier but handles
     more edge cases (age-gated, region-locked, different subtitle tracks).
     Public-domain / Unlicense.
   - A hybrid: try youtube-transcript-api first, fall back to yt-dlp for
     videos it can't handle.

2. **Whisper fallback** for videos with no subtitles at all. Explicitly
   out of scope for v1 — too heavy (model weights, GPU/CPU cost, ffmpeg).
   Recorded here so we don't forget it as a later option.

3. **CLI surface.** Flags likely needed: `--input <file>`, `--output-dir`,
   `--parallel N`, `--lang en,...`, `--skip-existing`, `--on-error {skip,abort}`.

4. **Metadata sourcing.** Title / channel / duration come from YouTube's
   oEmbed endpoint or the page HTML — cheapest path TBD.

5. **Rate limiting / proxy strategy.** YouTube aggressively throttles bulk
   transcript fetches. May need configurable delay, retry-with-backoff,
   or proxy rotation for large batches.

## What's here right now

Just this README. No `upstream/`, no `LICENSE`, no `UPSTREAM.txt` yet —
those land when an upstream is chosen. Folder exists so the bwtools index
can point at it and so `git log` (if we ever make this a repo) records
when the intent was declared.
