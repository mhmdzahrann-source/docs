#!/usr/bin/env python3
"""Remove silent / dead-air parts from a video (jump-cut style) with ffmpeg.

Usage:
    python3 cut_silence.py INPUT OUTPUT [--threshold -30] [--min-silence 0.4]
                                        [--padding 0.12] [--dry-run]

How it works:
    1. ffmpeg `silencedetect` finds every stretch quieter than --threshold dB
       that lasts at least --min-silence seconds.
    2. The parts *between* silences are kept, with --padding seconds added on
       each side so words don't get clipped.
    3. The kept parts are joined with ffmpeg trim/atrim + concat (frame
       accurate, audio and video stay in sync).

Requires: ffmpeg + ffprobe on PATH. No Python packages needed.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
         "-of", "json", path],
        check=True, capture_output=True, text=True,
    ).stdout
    info = json.loads(out)
    duration = float(info["format"]["duration"])
    types = {s["codec_type"] for s in info.get("streams", [])}
    return duration, "video" in types, "audio" in types


def detect_silences(path, threshold_db, min_silence):
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af",
         f"silencedetect=noise={threshold_db}dB:d={min_silence}", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    silences, start = [], None
    for line in result.stderr.splitlines():
        m = re.search(r"silence_start: (-?[\d.]+)", line)
        if m:
            start = max(0.0, float(m.group(1)))
            continue
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and start is not None:
            silences.append((start, float(m.group(1))))
            start = None
    return silences, start  # trailing `start` = silence running to the end


def keep_segments(duration, silences, open_start, padding, min_keep=0.15):
    if open_start is not None:
        silences.append((open_start, duration))
    keeps, cursor = [], 0.0
    for s_start, s_end in silences:
        if s_start > cursor:
            keeps.append((cursor, s_start))
        cursor = max(cursor, s_end)
    if cursor < duration:
        keeps.append((cursor, duration))

    padded = []
    for a, b in keeps:
        a, b = max(0.0, a - padding), min(duration, b + padding)
        if padded and a <= padded[-1][1]:
            padded[-1] = (padded[-1][0], max(padded[-1][1], b))
        else:
            padded.append((a, b))
    return [(a, b) for a, b in padded if b - a >= min_keep]


def build_filter(segments, has_video, has_audio):
    parts, labels = [], []
    for i, (a, b) in enumerate(segments):
        if has_video:
            parts.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}]")
            labels.append(f"[v{i}]")
        if has_audio:
            parts.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[a{i}]")
            labels.append(f"[a{i}]")
    outs = ("[outv]" if has_video else "") + ("[outa]" if has_audio else "")
    parts.append(f"{''.join(labels)}concat=n={len(segments)}:v={int(has_video)}:a={int(has_audio)}{outs}")
    return ";\n".join(parts)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--threshold", type=float, default=-30.0,
                   help="dB level counted as silence (default -30; use -35/-40 for quiet speakers, -25 for noisy rooms)")
    p.add_argument("--min-silence", type=float, default=0.4,
                   help="shortest pause (s) to cut (default 0.4; 0.25 = aggressive TikTok pace, 0.7 = natural)")
    p.add_argument("--padding", type=float, default=0.12,
                   help="seconds kept around speech so words aren't clipped (default 0.12)")
    p.add_argument("--crf", type=int, default=20, help="x264 quality, lower = better (default 20)")
    p.add_argument("--dry-run", action="store_true", help="only print what would be cut")
    args = p.parse_args()

    duration, has_video, has_audio = probe(args.input)
    if not has_audio:
        sys.exit("No audio stream: silence cutting needs audio.")

    silences, open_start = detect_silences(args.input, args.threshold, args.min_silence)
    segments = keep_segments(duration, silences, open_start, args.padding)
    if not segments:
        sys.exit("Everything was detected as silence: try a lower --threshold (e.g. -40).")

    kept = sum(b - a for a, b in segments)
    print(f"Input: {duration:.2f}s | keeping {len(segments)} segments = {kept:.2f}s "
          f"| removed {duration - kept:.2f}s ({100 * (duration - kept) / duration:.0f}%)")
    if args.dry_run:
        for a, b in segments:
            print(f"  keep {a:8.2f} -> {b:8.2f}")
        return

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(build_filter(segments, has_video, has_audio))
        script = f.name

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", args.input,
           "-filter_complex_script", script]
    if has_video:
        cmd += ["-map", "[outv]", "-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf),
                "-pix_fmt", "yuv420p"]
    cmd += ["-map", "[outa]", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", args.output]
    subprocess.run(cmd, check=True)
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
