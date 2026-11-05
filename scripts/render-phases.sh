#!/usr/bin/env bash
# Render phase frames of a CSS-animated fragment with headless Chrome, plus a contact sheet.
#
# Usage: render-phases.sh <fragment-dir> <W> <H> <seconds...> [rest]
#   fragment-dir must contain <name>.html where <name> = basename of the dir.
#   Each <seconds> value renders phase-<s>.png at that point of the cycle;
#   "rest" renders the ungated resting frame (what PDF export sees).
#   contact.png puts all rendered phases side by side with their labels.
#
# Environment (all optional):
#   CHROME     path to a Chrome/Chromium/Edge binary (auto-detected otherwise)
#   BG         page background behind the fragment (default #0f1218 = --anim-bg fallback)
#   GATE       class put on the wrapping <section> for animated frames (default visible)
#   FONTS_CSS  a <link> or <style> string injected into the preview head (host fonts)
#   THEME_CSS  path to a CSS file injected into the preview (e.g. :root{--anim-theme-*:...})
#
# Method: a preview copy with negative animation-delay + animation-play-state: paused,
# which freezes every CSS animation exactly at second N of its cycle.
# Do NOT use --virtual-time-budget: it desyncs compositor and main-thread animations.
set -euo pipefail
[ $# -ge 4 ] || { echo "usage: $0 <fragment-dir> <W> <H> <seconds...> [rest]" >&2; exit 2; }
DIR="$(cd "$1" && pwd)"; W="$2"; H="$3"; shift 3
NAME="$(basename "$DIR")"
FRAG="$DIR/$NAME.html"
[ -f "$FRAG" ] || { echo "missing $FRAG (the file must be named after its directory)" >&2; exit 1; }

find_chrome() {
  local c
  for c in \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/Applications/Chromium.app/Contents/MacOS/Chromium" \
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
    "$HOME/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; do
    [ -x "$c" ] && { echo "$c"; return; }
  done
  for c in google-chrome google-chrome-stable chromium chromium-browser microsoft-edge; do
    command -v "$c" >/dev/null 2>&1 && { command -v "$c"; return; }
  done
}
CHROME="${CHROME:-$(find_chrome)}"
if [ -z "$CHROME" ] || ! { [ -x "$CHROME" ] || command -v "$CHROME" >/dev/null 2>&1; }; then
  echo "error: no Chrome/Chromium/Edge found; set CHROME=/path/to/chrome" >&2; exit 1
fi

BG="${BG:-#0f1218}"
GATE="${GATE:-visible}"
FONTS_CSS="${FONTS_CSS:-}"
THEME=""
if [ -n "${THEME_CSS:-}" ]; then
  [ -f "$THEME_CSS" ] || { echo "THEME_CSS file not found: $THEME_CSS" >&2; exit 1; }
  THEME="<style>$(cat "$THEME_CSS")</style>"
fi

shoot() {  # $1 = png, $2 = html, $3 = width, $4 = height
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --window-size="$3,$4" --screenshot="$1" "file://$2" >/dev/null 2>&1
}

make_preview() {  # $1 = output file, $2 = section class, $3 = extra style
  {
    echo "<!doctype html><meta charset=utf-8>$FONTS_CSS$THEME"
    echo "<style>html,body{margin:0;background:$BG}section{width:${W}px;height:${H}px}$3</style>"
    echo "<section class=\"$2\">"; cat "$FRAG"; echo "</section>"
  } > "$1"
}

SHOTS=()
for s in "$@"; do
  if [ "$s" = "rest" ]; then
    make_preview "$DIR/preview-rest.html" "" ""
  else
    make_preview "$DIR/preview-$s.html" "$GATE" \
      ".$GATE *{animation-delay:-${s}s !important;animation-play-state:paused !important}"
  fi
  shoot "$DIR/phase-$s.png" "$DIR/preview-$s.html" "$W" "$H"
  [ -f "$DIR/phase-$s.png" ] || { echo "screenshot failed for phase $s" >&2; exit 1; }
  SHOTS+=("$s")
  echo "rendered $DIR/phase-$s.png"
done

# contact sheet: phases side by side (wrapping), each scaled to 480 px wide, with its label
TW=480; TH=$(( H * TW / W )); N=${#SHOTS[@]}
COLS=$(( N < 4 ? N : 4 )); ROWS=$(( (N + COLS - 1) / COLS ))
CW=$(( COLS * (TW + 16) + 16 )); CH=$(( ROWS * (TH + 44) + 16 ))
{
  echo "<!doctype html><meta charset=utf-8><style>html,body{margin:0;background:#222;font:16px system-ui,sans-serif;color:#ddd}"
  echo ".w{display:flex;flex-wrap:wrap;gap:16px;padding:16px 0 0 16px}figure{margin:0;width:${TW}px}"
  echo "img{width:${TW}px;height:${TH}px;display:block;outline:1px solid #555}figcaption{height:28px;line-height:28px}</style><div class=w>"
  for s in "${SHOTS[@]}"; do
    label="${s}s"; [ "$s" = "rest" ] && label="rest (ungated)"
    echo "<figure><img src=\"phase-$s.png\"><figcaption>$NAME &middot; $label</figcaption></figure>"
  done
  echo "</div>"
} > "$DIR/contact.html"
shoot "$DIR/contact.png" "$DIR/contact.html" "$CW" "$CH"
echo "rendered $DIR/contact.png"
echo "now LOOK at $DIR/phase-*.png and contact.png with your image viewing tool; fix and re-run."
