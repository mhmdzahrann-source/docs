---
name: video-cut
description: Cut and tighten talking videos for Reels/TikTok/Shorts - remove silences and dead air (jump cuts), trim start/end, cut to a target length, reframe to vertical 9:16, and export platform-ready MP4. Use when the user asks to cut, trim, tighten, shorten, remove pauses/silence, make jump cuts, or turn a video into a reel/short.
---

# Video cutting

All edits use **ffmpeg** (must be installed: `brew install ffmpeg` on Mac).
Never overwrite the user's original file - always write a new output file,
e.g. `name_cut.mp4`.

## Standard workflow for a talking video

Run these in order (each step's output feeds the next):

1. **Clean audio first** (better audio = more accurate silence detection):
   use the `audio-cleanup` skill.
2. **Remove silences** with the bundled script:
   ```bash
   python3 .claude/skills/video-cut/scripts/cut_silence.py in.mp4 out_cut.mp4 --dry-run   # preview
   python3 .claude/skills/video-cut/scripts/cut_silence.py in.mp4 out_cut.mp4
   ```
   Pick the pace:
   | Style | `--min-silence` | `--padding` |
   |---|---|---|
   | Natural (podcast, tutorial) | 0.7 | 0.20 |
   | Default (most reels) | 0.4 | 0.12 |
   | Fast TikTok jump-cut | 0.25 | 0.08 |

   If it cuts words: raise `--padding` or lower `--threshold` (e.g. `-38`).
   If it leaves pauses in a noisy room: raise `--threshold` (e.g. `-25`).
3. **Reframe to vertical** (if the source is horizontal), see below.
4. **Check length** against the target platform, see the table at the end.
5. Report to the user: original length, new length, % removed, output path.

## Common commands

Trim (keep 00:05 to 00:35, frame-accurate):
```bash
ffmpeg -ss 5 -to 35 -i in.mp4 -c:v libx264 -crf 20 -c:a aac out.mp4
```

Horizontal 16:9 -> vertical 9:16 (center crop, 1080x1920):
```bash
ffmpeg -i in.mp4 -vf "crop=ih*9/16:ih,scale=1080:1920" -c:v libx264 -crf 20 -c:a copy out_vertical.mp4
```

Vertical with blurred background (keeps the whole frame, no crop):
```bash
ffmpeg -i in.mp4 -filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20[bg];[0:v]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2" -c:v libx264 -crf 20 -c:a copy out_vertical.mp4
```

Speed up 1.1x (feels snappier, still natural):
```bash
ffmpeg -i in.mp4 -filter_complex "[0:v]setpts=PTS/1.1[v];[0:a]atempo=1.1[a]" -map "[v]" -map "[a]" out_fast.mp4
```

Join clips (same codec/size):
```bash
printf "file '%s'\n" clip1.mp4 clip2.mp4 > list.txt
ffmpeg -f concat -safe 0 -i list.txt -c copy joined.mp4
```

Extract a cover/thumbnail frame:
```bash
ffmpeg -ss 1.5 -i in.mp4 -frames:v 1 -q:v 2 thumb.jpg
```

## Editing rules for viral pacing

- **The first 1-2 seconds decide everything.** Cut any "hi guys", breath,
  or setup before the first real sentence. Start on the hook.
- No pause longer than ~0.4s unless it's for comedic or dramatic effect.
- Cut the ending right after the payoff/CTA - no fade-out, no "bye".
- For loops: end on a frame/sentence that flows back into the start.
- See `research/viral-video-rnd.md` for formats and hooks.

## Platform export targets

| Platform | Size | Best length | Max |
|---|---|---|---|
| Instagram Reels | 1080x1920 | 7-30s (up to 90s if retention is strong) | 3 min |
| TikTok | 1080x1920 | 15-60s; 60s+ if retention holds | 10 min |
| YouTube Shorts | 1080x1920 | 20-45s | 3 min |

Export: H.264, `-crf 18-20`, AAC 192k, `-movflags +faststart`, 30fps.
