---
name: viral-research
description: Research which short-form videos (Reels, TikTok, Shorts) are going viral in a niche, break down their hook/format/pacing, and turn them into original video ideas and scripts for the user. Use when the user asks what's trending, what goes viral, for video ideas, to "clone" or recreate a viral video/format, or for content R&D.
---

# Viral video R&D

Base knowledge (formats, hooks, platform signals, ideas):
`research/viral-video-rnd.md`. Read it first, then refresh it with new
searches because trends change weekly.

## The one rule: clone the format, never the content

When the user says "clone this viral video", recreate the **structure**
(hook pattern, format, pacing, length, caption style, CTA) with **their own**
footage, words and voice. Do not download and re-upload other people's
videos, copy their script word-for-word, imitate a real person's voice, or
use copyrighted music outside the platform's in-app library. Explain this
briefly if asked. It's also better for reach, since platforms down-rank
reposts.

## Workflow

1. **Clarify** (only if unknown): niche, platform, target audience, goal
   (followers, leads/DMs, sales).
2. **Search** (run searches in parallel, prefer the last 30 days):
   - `"<niche>" viral reels <month year>`
   - `tiktok trending <niche> format <month year>`
   - `<niche> hooks that went viral`
   - TikTok Creative Center trends, if reachable.
   If the user gives specific viral video links, break those down instead.
3. **Break down** each example into a table: Hook (line + first frame) |
   Format (match the format table in the R&D doc) | Length | Cuts per 10s |
   Captions | Audio | CTA | Why it spread (sends / saves / comments / rewatch).
4. **Generate 5 ideas** for the user's niche, each with:
   - Format name and the viral example it's modelled on
   - Hook line (≤ 10 words) plus first-frame visual
   - Script: beat-by-beat with timestamps, total 15-45s
   - Shot list (what to film on a phone)
   - Edit recipe: `audio-cleanup` level, `video-cut` pace
     (natural/default/fast), vertical method, caption style
   - CTA. Prefer "Comment <KEYWORD>" when it can connect to the repo's
     Instagram comment-to-DM tool.
5. **Save** the findings: append a dated section to
   `research/viral-video-rnd.md` (or a new `research/<niche>-<date>.md`)
   with sources as markdown links.
6. **After filming**, hand off to `audio-cleanup` then `video-cut`.

## Optional tools if connected

- A virality predictor / video analysis tool (e.g. the Higgsfield
  connector's `virality_predictor`) can score a finished cut's hook
  strength and retention risk before posting. Ask before using paid tools.
- ElevenLabs connector: voice-overs and transcription for captions. Ask
  before spending credits.

## Output to the user

Keep the chat reply short: top 3 formats, 5 hook lines, and the best idea's
script. Put the full breakdown in the research file and link it.
