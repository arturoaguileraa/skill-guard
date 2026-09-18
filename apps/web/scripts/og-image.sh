#!/usr/bin/env bash
# Regenerate public/og.png — the link-preview image WhatsApp / LinkedIn / X show.
# It is a real screenshot of the landing page (what a visitor sees on entering),
# so re-run it whenever the first screen changes:
#
#   bash apps/web/scripts/og-image.sh [url]     # default: the production site
#
# macOS only (Google Chrome headless + sips). Output: 1200x628 (~1.91:1, the
# ratio the platforms crop to), PNG, kept small: WhatsApp drops large previews.
set -euo pipefail

URL="${1:-https://skill-guard-app.vercel.app/}"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
OUT="$(cd "$(dirname "$0")/.." && pwd)/public/og.png"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# 1920x1005 shows the hero, the presets, the editor and the whole verdict dial;
# --virtual-time-budget lets the live analysis answer before the shot is taken.
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
  --window-size=1920,1005 --virtual-time-budget=12000 \
  --screenshot="$TMP/full.png" "$URL" >/dev/null 2>&1

# Crop the empty side margins to 1.91:1 (1700x890), then scale to 1200x628.
sips --cropToHeightWidth 890 1700 --cropOffset 0 110 "$TMP/full.png" --out "$TMP/crop.png" >/dev/null
sips -z 628 1200 "$TMP/crop.png" --out "$OUT" >/dev/null

echo "wrote $OUT ($(wc -c <"$OUT" | tr -d ' ') bytes)"
