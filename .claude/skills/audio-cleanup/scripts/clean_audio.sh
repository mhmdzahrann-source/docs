#!/usr/bin/env bash
# Clean up the voice track of a video (or audio file): remove background
# noise/hum, tame harsh highs, and normalise loudness for social media.
#
# Usage:
#   clean_audio.sh INPUT OUTPUT [light|medium|strong] [rnnoise_model.rnnn]
#
#   light  - gentle, keeps room feel (good mics, quiet rooms)
#   medium - default; fans, AC, street hum
#   strong - very noisy rooms; may sound slightly "processed"
#   4th arg (optional): path to an RNNoise model -> uses neural denoising
#   (ffmpeg arnndn) instead of the FFT denoiser. Models:
#   https://github.com/GregorR/rnnoise-models  (e.g. beguiling-drafter/bd.rnnn)
#
# The video stream is copied untouched (no quality loss, very fast).
# Loudness target: -14 LUFS / -1.5 dBTP (Instagram, TikTok, YouTube standard).
set -euo pipefail

if [[ $# -lt 2 ]]; then
  sed -n '2,17p' "$0"; exit 1
fi

IN="$1"; OUT="$2"; LEVEL="${3:-medium}"; MODEL="${4:-}"

case "$LEVEL" in
  light)  DENOISE="afftdn=nr=8:nf=-45:tn=1" ;;
  medium) DENOISE="afftdn=nr=14:nf=-35:tn=1" ;;
  strong) DENOISE="afftdn=nr=24:nf=-28:tn=1,afftdn=nr=10:nf=-30" ;;
  *) echo "Level must be light, medium or strong"; exit 1 ;;
esac

if [[ -n "$MODEL" ]]; then
  [[ -f "$MODEL" ]] || { echo "Model not found: $MODEL"; exit 1; }
  DENOISE="arnndn=m='${MODEL}':mix=0.9"
fi

# 1. highpass   - removes rumble, AC hum, mic handling below 80 Hz
# 2. lowpass    - removes hiss above 14 kHz (above useful voice range)
# 3. denoise    - FFT (afftdn) or neural (arnndn) noise removal
# 4. deesser    - softens harsh "s" sounds
# 5. compressor - evens out loud/quiet words
# 6. loudnorm   - consistent platform loudness
FILTER="highpass=f=80,lowpass=f=14000,${DENOISE},deesser=i=0.4,acompressor=threshold=-20dB:ratio=3:attack=10:release=150:makeup=2,loudnorm=I=-14:TP=-1.5:LRA=11"

if ffprobe -v error -select_streams v -show_entries stream=index -of csv=p=0 "$IN" | grep -q .; then
  ffmpeg -y -hide_banner -loglevel error -i "$IN" -map 0:v:0 -map 0:a:0 \
    -c:v copy -af "$FILTER" -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$OUT"
else
  ffmpeg -y -hide_banner -loglevel error -i "$IN" -af "$FILTER" -ar 48000 "$OUT"
fi
echo "Saved: $OUT (level: ${MODEL:+rnnoise}${MODEL:-$LEVEL})"
