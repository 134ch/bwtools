# yt-transcripts

**Status: stub. Not yet implemented.**

Planned tool: a bulk YouTube transcript extractor.

## Goal

Feed it a list of YouTube URLs, get back one Markdown file per video ready
to drop into an LLM pipeline or a markitdown-converted document set.

## Planned I/O Contract

**Input:** a text file with one YouTube URL per line, or stdin.

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
turn - decision deferred to build time]
```

This output shape is deliberately aligned with how `../markitdown/` emits
files, so downstream tooling can consume both interchangeably.

## Install

There are no runtime dependencies yet:

```bash
python -m pip install -r requirements.txt
```

That command is currently a no-op and exists so scripts can use the same
install convention for every tool folder.

## Open Decisions

1. **Extraction backend.** Candidates:
   - [`jdepoix/youtube-transcript-api`](https://github.com/jdepoix/youtube-transcript-api)
     - pure Python, MIT, lightweight. Works for most public videos. No audio
     download, no ffmpeg.
   - [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) - much heavier but handles
     more edge cases: age-gated, region-locked, different subtitle tracks.
     Public-domain / Unlicense.
   - A hybrid: try youtube-transcript-api first, fall back to yt-dlp for
     videos it cannot handle.

2. **Whisper fallback** for videos with no subtitles at all. Explicitly out of
   scope for v1 - too heavy: model weights, GPU/CPU cost, and ffmpeg.

3. **CLI surface.** Flags likely needed: `--input <file>`, `--output-dir`,
   `--parallel N`, `--lang en,...`, `--skip-existing`, and
   `--on-error {skip,abort}`.

4. **Metadata sourcing.** Title, channel, and duration can come from YouTube's
   oEmbed endpoint or the page HTML. Cheapest path is still TBD.

5. **Rate limiting / proxy strategy.** YouTube aggressively throttles bulk
   transcript fetches. Large batches may need configurable delay,
   retry-with-backoff, or proxy rotation.

## What's here right now

Just this README and an empty `requirements.txt`. No `upstream/`, no
`LICENSE`, no `UPSTREAM.txt` yet. Those land when an upstream is chosen.
Folder exists so the bwtools index can point at it and so git history records
when the intent was declared.
