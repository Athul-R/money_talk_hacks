#!/usr/bin/env bash
# Convert the Playwright recording into a GitHub-friendly README GIF.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
META="$HERE/raw/meta.json"
VIDEO="$(python3 -c "import json; print(json.load(open('$META'))['video'])")"
START="$(python3 -c "import json; print(json.load(open('$META'))['startOffsetSec'])")"
DURATION="$(python3 -c "import json; print(json.load(open('$META'))['durationSec'])")"
OUT="$HERE/../../../docs/assets/workflow.gif"

encode() {
  local width="$1"
  local fps="$2"
  local colors="$3"
  ffmpeg -y -loglevel error -ss "$START" -t "$DURATION" -i "$VIDEO" \
    -filter_complex \
    "[0:v]fps=$fps,scale=$width:-1:flags=lanczos,split[a][b]; \
     [a]palettegen=max_colors=$colors:stats_mode=diff[p]; \
     [b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" \
    "$OUT"
}

encode 1080 12 96
SIZE="$(stat -f%z "$OUT")"
if [ "$SIZE" -gt 6000000 ]; then encode 960 10 72; SIZE="$(stat -f%z "$OUT")"; fi
if [ "$SIZE" -gt 6000000 ]; then encode 840 9 56; SIZE="$(stat -f%z "$OUT")"; fi

echo "workflow GIF: $OUT ($((SIZE / 1024)) KB)"
