---
name: audio-cleanup
description: Remove background noise, hum, hiss and echo-y harshness from a video's or audio file's voice track, and normalise loudness for social media (-14 LUFS). Use when the user mentions noise, background sound, hum, fan, AC, wind, bad audio, quiet/loud voice, or "make the sound better" for a video.
---

# Audio cleanup

Uses **ffmpeg** only. The video stream is copied untouched, so this is fast
and loses no picture quality. Never overwrite the original - write
`name_clean.mp4`.

## Quick use

```bash
.claude/skills/audio-cleanup/scripts/clean_audio.sh in.mp4 in_clean.mp4 medium
```

| Level | When |
|---|---|
| `light` | Good mic, quiet room - just polish + loudness |
| `medium` | Default. Fan, AC, computer hum, light street noise |
| `strong` | Loud background (cafe, car, wind). May sound slightly processed |

### Neural denoising (best quality for voice)

For hard cases, use RNNoise (ffmpeg's `arnndn` filter) - download a model
once from https://github.com/GregorR/rnnoise-models (e.g.
`beguiling-drafter-2018-08-30/bd.rnnn`), then:

```bash
.claude/skills/audio-cleanup/scripts/clean_audio.sh in.mp4 in_clean.mp4 medium path/to/bd.rnnn
```

## What the chain does

`highpass 80Hz` (rumble/hum) -> `lowpass 14kHz` (hiss) -> denoise
(`afftdn` or `arnndn`) -> `deesser` (harsh "s") -> `acompressor` (even
volume) -> `loudnorm -14 LUFS` (platform standard).

## Workflow

1. Listen/measure first:
   ```bash
   ffmpeg -i in.mp4 -af volumedetect -f null - 2>&1 | grep -E "mean|max"
   ```
2. Start with `medium`. If voice sounds robotic/watery -> `light`.
   If noise is still audible -> `strong` or the RNNoise model.
3. Run this **before** `video-cut` - cleaner audio gives more accurate
   silence detection.
4. Tell the user which level was used and suggest they listen on
   headphones and on a phone speaker.

## Extra fixes

Add background music under the voice (music auto-ducks when speaking):
```bash
ffmpeg -i video.mp4 -i music.mp3 -filter_complex "[1:a]volume=0.25[m];[m][0:a]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[duck];[0:a][duck]amix=inputs=2:duration=first:normalize=0[a]" -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k out_music.mp4
```

Remove a single constant hum (e.g. 50Hz in Europe/Middle East, 60Hz in US):
```bash
ffmpeg -i in.mp4 -af "bandreject=f=50:width_type=h:w=4,bandreject=f=100:width_type=h:w=4" -c:v copy out.mp4
```

Only use music the user has rights to (their own, licensed, or the
platform's in-app library added when posting).
