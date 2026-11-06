#!/usr/bin/env bash
# Render phase frames of a CSS-animated fragment or host page with headless Chrome, plus a contact sheet.
#
# Usage:
#   render-phases.sh [--out DIR] [--theme FILE] <fragment-dir | fragment.html> <W> <H> <seconds...> [rest]
#   render-phases.sh [--out DIR] [--theme FILE] --page <page.html> [--slide N|#hash|selector] [--no-script] <W> <H> <seconds...> [rest]
#
#   Fragment mode: a directory means <dir>/<basename of dir>.html (or the only .html in it);
#   a file path is used as is. The fragment is wrapped in <section class="$GATE"> of W x H.
#   Page mode (--page): a whole host page, shot in a W x H window. Its own gate class
#   (<section class="visible">) is kept for the seconds and removed from every element for "rest".
#
#   --slide S  (page mode) shoot one slide of a multi-slide page. S is
#                N         the Nth slide (Nth .slide element, else Nth <section>); the URL also
#                          gets #N, which decks with hash routing (md_to_deck.py: #N / #sN) follow
#                #hash     open the page at that URL fragment (#s26, #/25, ...) and nothing else
#                selector  any CSS selector (e.g. 'section#s26'); quote it in the shell
#              For N and selector, a script injected before </body> hides the other slides
#              (same tag, display:none), brings that one into view and, for the seconds, puts the
#              gate class on it and removes it from every other element; for "rest" it removes the
#              gate class from every element. Prefer N or a selector over #hash: headless
#              --screenshot paints content reached by scrolling a long page black.
#   --no-script  strip the page's own <script> elements (inline and src) from the preview copies.
#              Use it whenever the page's own script toggles the gate class (deck navigation,
#              an observer): with scripts running, "rest" is re-gated by the page and does not
#              show the resting frame that print/PDF shows. md_to_deck.py decks without script
#              stack every slide at stage size, so --slide N still lands on slide N.
#              The --slide helper script is injected after stripping and still runs.
#
#   Each <seconds> value renders phase-<s>.png paused at that point of the cycle;
#   "rest" renders the ungated resting frame (what PDF export sees).
#   contact.png puts all rendered phases side by side with their labels.
#
#   --theme FILE  a host theme CSS file (host_theme.py output: match or lean), injected as a
#              <style> into the preview head, before the fragment's own style (same as THEME_CSS).
#              Fragment mode: the wrapper <section> also gets class anim-lean, and the page
#              background becomes var(--anim-theme-bg, BG), so a match theme shows on the host
#              ground and a lean theme on the lean ground. Render one fragment twice
#              (--theme match.css, --theme lean.css, separate --out) for the intake sample.
#
#   --out DIR  where preview-*.html, phase-*.png and contact.* go (created if missing).
#              Default: a new temp directory, printed at the start and the end. The source
#              folder is never written to unless you pass it as --out.
#
# Environment (all optional):
#   CHROME     path to a Chrome/Chromium/Edge binary (auto-detected otherwise)
#   BG         fragment mode: page background behind the fragment (default #0F1E27 = --anim-bg fallback)
#   GATE       gate class (default visible): put on the wrapper in fragment mode, stripped for rest in page mode
#   FONTS_CSS  a <link> or <style> string injected into the preview head (host fonts)
#   THEME_CSS  path to a CSS file injected into the preview (e.g. :root{--anim-theme-*:...});
#              --theme FILE overrides it
#
# Method: a preview copy with negative animation-delay + animation-play-state: paused,
# which freezes every CSS animation exactly at second N of its cycle.
# Do NOT use --virtual-time-budget: it desyncs compositor and main-thread animations.
# No GIF output: that needs an encoder (ffmpeg, ImageMagick) this script does not depend on.
set -euo pipefail
USAGE="usage: $0 [--out DIR] [--theme FILE] <fragment-dir|fragment.html> <W> <H> <seconds...> [rest]
       $0 [--out DIR] [--theme FILE] --page <page.html> [--slide N|#hash|selector] [--no-script] <W> <H> <seconds...> [rest]"

OUT=""; PAGE=""; SLIDE=""; NOSCRIPT=""; ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --out) [ $# -ge 2 ] || { echo "$USAGE" >&2; exit 2; }; OUT="$2"; shift 2 ;;
    --out=*) OUT="${1#--out=}"; shift ;;
    --page) [ $# -ge 2 ] || { echo "$USAGE" >&2; exit 2; }; PAGE="$2"; shift 2 ;;
    --page=*) PAGE="${1#--page=}"; shift ;;
    --slide) [ $# -ge 2 ] || { echo "$USAGE" >&2; exit 2; }; SLIDE="$2"; shift 2 ;;
    --slide=*) SLIDE="${1#--slide=}"; shift ;;
    --no-script) NOSCRIPT=1; shift ;;
    --theme) [ $# -ge 2 ] || { echo "$USAGE" >&2; exit 2; }; THEME_CSS="$2"; shift 2 ;;
    --theme=*) THEME_CSS="${1#--theme=}"; shift ;;
    -h|--help) echo "$USAGE"; exit 0 ;;
    --) shift; ARGS+=("$@"); break ;;
    -*) echo "unknown option $1" >&2; echo "$USAGE" >&2; exit 2 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
set -- "${ARGS[@]+"${ARGS[@]}"}"

if [ -z "$PAGE" ] && { [ -n "$SLIDE" ] || [ -n "$NOSCRIPT" ]; }; then
  echo "--slide and --no-script need --page" >&2; exit 2
fi
HASH=""
case "$SLIDE" in
  "") ;;
  \#*) HASH="$SLIDE" ;;
  *) [[ "$SLIDE" =~ ^[0-9]+$ ]] && { [ "$SLIDE" -ge 1 ] || { echo "--slide N starts at 1" >&2; exit 2; }; HASH="#$SLIDE"; } ;;
esac
[ -z "$HASH" ] || [[ "$HASH" =~ ^#[A-Za-z0-9/_.:-]*$ ]] || { echo "--slide #hash: letters, digits and / _ . : - only" >&2; exit 2; }

abspath() { (cd "$(dirname "$1")" && echo "$(pwd)/$(basename "$1")"); }

if [ -n "$PAGE" ]; then
  [ $# -ge 3 ] || { echo "$USAGE" >&2; exit 2; }
  [ -f "$PAGE" ] || { echo "missing page $PAGE" >&2; exit 1; }
  SRC="$(abspath "$PAGE")"; W="$1"; H="$2"; shift 2
else
  [ $# -ge 4 ] || { echo "$USAGE" >&2; exit 2; }
  if [ -d "$1" ]; then
    D="$(cd "$1" && pwd)"; SRC="$D/$(basename "$D").html"
    if [ ! -f "$SRC" ]; then
      cands=()
      for f in "$D"/*.html; do
        case "$(basename "$f")" in preview-*.html|contact.html) ;; *) [ -f "$f" ] && cands+=("$f") ;; esac
      done
      [ ${#cands[@]} -eq 1 ] || { echo "missing $SRC (name it after the directory, or pass the .html file)" >&2; exit 1; }
      SRC="${cands[0]}"
    fi
  else
    [ -f "$1" ] || { echo "missing fragment $1" >&2; exit 1; }
    SRC="$(abspath "$1")"
  fi
  W="$2"; H="$3"; shift 3
fi
NAME="$(basename "$SRC" .html)"
SRCDIR="$(dirname "$SRC")"
for v in "$W" "$H"; do [[ "$v" =~ ^[0-9]+$ ]] || { echo "W and H must be integers, got $v" >&2; exit 2; }; done
for s in "$@"; do
  [ "$s" = "rest" ] || [[ "$s" =~ ^[0-9]+([.][0-9]+)?$ ]] || { echo "phase must be seconds or rest, got $s" >&2; exit 2; }
done

if [ -z "$OUT" ]; then
  OUT="$(mktemp -d "${TMPDIR:-/tmp}/render-phases.$NAME.XXXXXX")"
else
  mkdir -p "$OUT"
fi
OUT="$(cd "$OUT" && pwd)"
echo "output: $OUT"

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

BG="${BG:-#0F1E27}"
PAGE_BG="$BG"; WRAP_CLASS=""
GATE="${GATE:-visible}"
[[ "$GATE" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]] || { echo "GATE must be a single class name" >&2; exit 2; }
FONTS_CSS="${FONTS_CSS:-}"
THEME=""
if [ -n "${THEME_CSS:-}" ]; then
  [ -f "$THEME_CSS" ] || { echo "THEME_CSS file not found: $THEME_CSS" >&2; exit 1; }
  THEME="<style>$(cat "$THEME_CSS")</style>"
  PAGE_BG="var(--anim-theme-bg,$BG)"; WRAP_CLASS="anim-lean"  # lean themes scope to .anim-lean
fi
BASE="<base href=\"file://$SRCDIR/\">"  # previews live in OUT; relative assets still resolve

shoot() {  # $1 = png, $2 = html, $3 = width, $4 = height, $5 = optional #fragment
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --window-size="$3,$4" --screenshot="$1" "file://$2${5:-}" >/dev/null 2>&1
}

pause_css() { echo ".$GATE *{animation-delay:-${1}s !important;animation-play-state:paused !important}"; }

make_fragment_preview() {  # $1 = output file, $2 = section class, $3 = extra style
  {
    echo "<!doctype html><meta charset=utf-8>$BASE$FONTS_CSS$THEME"
    echo "<style>html,body{margin:0;background:$PAGE_BG}section{width:${W}px;height:${H}px}$3</style>"
    echo "<section class=\"$(echo $2 $WRAP_CLASS)\">"; cat "$SRC"; echo "</section>"
  } > "$1"
}

make_page_preview() {  # $1 = output file, $2 = "rest" or "", $3 = extra style
  HEAD="$BASE$FONTS_CSS$THEME" EXTRA="$3" STRIP="$2" GATE="$GATE" SLIDE="$SLIDE" NOSCRIPT="$NOSCRIPT" \
    python3 -I - "$SRC" "$1" <<'PY'
import json, os, re, sys
src, out = sys.argv[1], sys.argv[2]
html = open(src, encoding="utf-8", errors="replace").read()
if os.environ["NOSCRIPT"]:  # the page's own scripts must not re-add the gate
    html = re.sub(r"<script\b[^>]*>.*?</script\s*>", "", html, flags=re.I | re.S)
    html = re.sub(r"<script\b[^>]*/>", "", html, flags=re.I)
slide = os.environ["SLIDE"]
if slide and not slide.startswith("#"):
    nth = int(slide) if slide.isdigit() else 0
    js = """<script>(function(){var g=%s,rest=%s,n=%d,sel=%s,el=null;
if(n){var l=document.querySelectorAll('.slide');if(!l.length)l=document.querySelectorAll('section');el=l[n-1]||null;}
else{try{el=document.querySelector(sel);}catch(e){}}
if(!el){document.title='render-phases: no slide '+(n||sel);return;}
document.querySelectorAll('.'+g).forEach(function(x){if(rest||x!==el)x.classList.remove(g);});
if(!rest)el.classList.add(g);
var sib=n?l:el.parentElement.children;
Array.prototype.forEach.call(sib,function(x){if(x!==el&&x.tagName===el.tagName)x.style.setProperty('display','none','important');});
window.scrollTo(0,0);el.scrollIntoView({block:'start',inline:'start'});})();</script>""" % (
        json.dumps(os.environ["GATE"]), "true" if os.environ["STRIP"] else "false", nth,
        json.dumps(slide).replace("</", "<\\/"))
    end = list(re.finditer(r"</body\s*>", html, re.I))
    html = html[:end[-1].start()] + js + html[end[-1].start():] if end else html + js
if os.environ["STRIP"]:  # drop the gate class token from every class attribute
    gate = re.compile(r"(?<![\w-])%s(?![\w-])" % re.escape(os.environ["GATE"]))
    html = re.sub(r"""(\bclass\s*=\s*)(["'])(.*?)\2""",
                  lambda m: m.group(1) + m.group(2) + " ".join(gate.sub("", m.group(3)).split()) + m.group(2),
                  html, flags=re.I | re.S)
extra = "<style>%s</style>" % os.environ["EXTRA"] if os.environ["EXTRA"] else ""
m = re.search(r"<head\b[^>]*>", html, re.I)
if m:  # <base> first so relative URLs resolve; the pause style last so it wins ties
    html = html[:m.end()] + os.environ["HEAD"] + html[m.end():]
    end = re.search(r"</head\s*>", html, re.I)
    html = html[:end.start()] + extra + html[end.start():] if end else html.replace(
        os.environ["HEAD"], os.environ["HEAD"] + extra, 1)
else:
    html = os.environ["HEAD"] + extra + html
open(out, "w", encoding="utf-8").write(html)
PY
}

SHOTS=()
for s in "$@"; do
  P="$OUT/preview-$s.html"
  if [ -n "$PAGE" ]; then
    if [ "$s" = "rest" ]; then make_page_preview "$P" rest ""; else make_page_preview "$P" "" "$(pause_css "$s")"; fi
  else
    if [ "$s" = "rest" ]; then make_fragment_preview "$P" "" ""; else make_fragment_preview "$P" "$GATE" "$(pause_css "$s")"; fi
  fi
  rm -f "$OUT/phase-$s.png"
  shoot "$OUT/phase-$s.png" "$P" "$W" "$H" "$HASH"
  [ -f "$OUT/phase-$s.png" ] || { echo "screenshot failed for phase $s" >&2; exit 1; }
  SHOTS+=("$s")
  echo "rendered $OUT/phase-$s.png"
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
} > "$OUT/contact.html"
shoot "$OUT/contact.png" "$OUT/contact.html" "$CW" "$CH"
echo "rendered $OUT/contact.png"
echo "now LOOK at $OUT/phase-*.png and contact.png with your image viewing tool; fix and re-run."
