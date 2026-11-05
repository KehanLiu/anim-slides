#!/usr/bin/env python3
"""Turn a Markdown deck into one self-contained HTML slide deck.

Usage:
    md_to_deck.py deck.md [-o deck.html] [--title T] [--stage W H] [--theme light|dark]

Slides are split exactly as extract_slides.py splits them (`---` rules, else #/##
headings; remark `???` notes, `--` reveals, `.class[...]` wrappers and leading
`class:`/`layout:`/`background-*:` lines are handled the same way), so both tools
agree on slide numbers and titles.

Output: <section class="slide" id="sN" data-slide="N"> per slide on a W x H stage
(default 1920x1080) scaled to the window; keyboard navigation (arrows, space,
PageUp/PageDown, Home/End) and #N / #sN hash routing; the current slide gets the
class `visible`, which is the gate anim-slides fragments use. Speaker notes go to
<aside class="notes"> (hidden). Each slide ends with an empty flex box
<div class="slot" id="sN-slot"></div> that takes the free height. The body (bullets,
paragraphs, code) sits between <!-- sN-body --> and <!-- /sN-body --> comments inside
<div class="body">, the title stays outside. With integrate_fragment.py:
  replace the text:   --anchor '<!-- sN-body -->' --replace-until '<!-- /sN-body -->'
  keep it, add below: --anchor 'id="sN-slot">'
A fragment in the body takes the free height and the empty slot collapses.
Without JavaScript (or with scripts stripped) all slides are stacked one per
stage height with no gate class, so `file://deck.html#sN` shows slide N at rest.
Printing gives one slide per page with the resting frames (the gate class is
removed before printing).

Self-contained: no CDN, system fonts, raw HTML in the Markdown is escaped, local
images (png, jpg, gif, webp, svg, under the deck's folder) are inlined as data:
URIs, remote images become a text placeholder, external links keep their URL in
a title attribute only (no href), so nothing loads from the network.
"""
import argparse
import base64
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_slides import md_chunks, md_blocks, md_inline_text  # noqa: E402

MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
        ".webp": "image/webp", ".svg": "image/svg+xml"}
MAX_IMG = 8 * 1024 * 1024


class Ctx:
    def __init__(self, base):
        self.base = os.path.realpath(base)
        self.warnings = []
        self.missing = []   # relative image paths that are not next to the .md

    def image(self, alt, src):
        src = html.unescape(src).strip().split()[0] if src.strip() else ""
        label = html.escape(alt or os.path.basename(src) or "image")
        if re.match(r"^[a-z][a-z0-9+.-]*:|^//", src, re.I) or not src:
            self.warnings.append("remote or empty image not inlined: %s" % (src or "(empty)"))
            return '<span class="img-missing">[image: %s]</span>' % label
        path = os.path.realpath(os.path.join(self.base, src.split("#")[0].split("?")[0]))
        ext = os.path.splitext(path)[1].lower()
        if path.startswith(self.base + os.sep) and ext in MIME and not os.path.exists(path):
            self.missing.append(src)
            return '<span class="img-missing">[image: %s]</span>' % label
        if (not path.startswith(self.base + os.sep) or ext not in MIME or not os.path.isfile(path)
                or os.path.getsize(path) > MAX_IMG):
            self.warnings.append("image not inlined (missing, outside the deck folder, not an image "
                                 "or over 8 MB): %s" % src)
            return '<span class="img-missing">[image: %s]</span>' % label
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        return '<img alt="%s" src="data:%s;base64,%s">' % (html.escape(alt), MIME[ext], data)


def inline(s, ctx):
    """Markdown inline markup to HTML. Everything is escaped first; raw HTML stays text."""
    codes = []

    def keep(m):
        codes.append("<code>%s</code>" % html.escape(m.group(1)))
        return "\x00%d\x00" % (len(codes) - 1)
    s = re.sub(r"`([^`]+)`", keep, s)
    hard = s.endswith("  ")
    s = html.escape(s.strip(), quote=False)
    s = re.sub(r"\\([\\`*_{}\[\]()#+\-.!>~|])", lambda m: "\x01%d\x01" % ord(m.group(1)), s)
    s = re.sub(r"!\[([^\]]*)\]\(([^)]*)\)", lambda m: ctx.image(html.unescape(m.group(1)), m.group(2)), s)

    def link(m):
        text, url = m.group(1), html.unescape(m.group(2)).strip().split(" ")[0]
        if url.startswith("#"):
            return '<a href="%s">%s</a>' % (html.escape(url), text)
        return '<a class="ext" title="%s">%s</a>' % (html.escape(url), text)
    s = re.sub(r"\[([^\]]*)\]\(([^)]*)\)", link, s)
    s = re.sub(r"&lt;(https?://[^\s&]+)&gt;", lambda m: '<a class="ext" title="%s">%s</a>'
               % (m.group(1), m.group(1)), s)
    s = re.sub(r"(\*\*\*|___)(?=\S)(.+?)(?<=\S)\1", r"<strong><em>\2</em></strong>", s)
    s = re.sub(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", r"<strong>\2</strong>", s)
    s = re.sub(r"~~(?=\S)(.+?)(?<=\S)~~", r"<del>\1</del>", s)
    s = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"(?<![\w])_(?=\S)(.+?)(?<=\S)_(?![\w])", r"<em>\1</em>", s)
    s = re.sub("\x01(\\d+)\x01", lambda m: html.escape(chr(int(m.group(1))), quote=False), s)
    s = re.sub("\x00(\\d+)\x00", lambda m: codes[int(m.group(1))], s)
    return s + ("<br>" if hard else "")


def lines_html(lines, ctx):
    return " ".join(inline(ln, ctx) for ln in lines).replace("<br> ", "<br>")


def list_html(items, ctx):
    """Nested lists from indentation."""
    out, stack = [], []  # stack of (indent, tag)
    for it in items:
        tag = "ol" if it["ordered"] else "ul"
        while stack and it["indent"] < stack[-1][0]:
            out.append("</li></%s>" % stack.pop()[1])
        if not stack or it["indent"] > stack[-1][0]:
            start = ' start="%d"' % it["start"] if tag == "ol" and it["start"] != 1 else ""
            out.append("<%s%s>" % (tag, start))
            stack.append((it["indent"], tag))
        else:
            out.append("</li>")
        text = [x for k, x in it["lines"] if k == "t"]
        quote = [x for k, x in it["lines"] if k == "q"]
        out.append("<li>" + lines_html(text, ctx))
        if quote:
            out.append("<blockquote>%s</blockquote>" % lines_html(quote, ctx))
    while stack:
        out.append("</li></%s>" % stack.pop()[1])
    return "".join(out)


def blocks_html(blocks, ctx):
    out = []
    for b in blocks:
        if b[0] == "heading":
            out.append("<h%d>%s</h%d>" % (b[1], inline(b[2], ctx), b[1]))
        elif b[0] == "para":
            out.append("<p>%s</p>" % lines_html(b[1], ctx))
        elif b[0] == "quote":
            out.append("<blockquote><p>%s</p></blockquote>" % lines_html(b[1], ctx))
        elif b[0] == "list":
            out.append(list_html(b[1], ctx))
        elif b[0] == "table":
            rows = b[1]
            head = "".join("<th>%s</th>" % inline(c, ctx) for c in rows[0]) if rows else ""
            body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c, ctx) for c in r)
                           for r in rows[1:])
            out.append("<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (head, body))
        elif b[0] == "code":
            cls = ' class="language-%s"' % html.escape(b[1]) if b[1] else ""
            out.append("<pre><code%s>%s</code></pre>" % (cls, html.escape("\n".join(b[2]))))
    return "\n".join(out)


def slide_html(n, chunk, ctx):
    blocks = md_blocks(chunk["body"])
    title_i = next((i for i, b in enumerate(blocks) if b[0] == "heading" and md_inline_text(b[2])), None)
    title, level = "", 2
    if title_i is not None:
        level, title = blocks[title_i][1], blocks.pop(title_i)[2]
    cls = ["slide"]
    if level == 1 and title and len(blocks) <= 2 and not any(b[0] in ("list", "table", "code") for b in blocks):
        cls.append("cover")
    parts = ['<section class="%s" id="s%d" data-slide="%d">' % (" ".join(cls), n, n)]
    if title:  # the title is always an <h1>, so HTML extraction picks the same title
        parts.append('<h1 class="slide-title lvl-%d">%s</h1>' % (level, inline(title, ctx)))
    # the body markers let integrate_fragment.py replace the text with a fragment:
    # --anchor '<!-- sN-body -->' --replace-until '<!-- /sN-body -->' (Markdown HTML is escaped,
    # so no slide text can contain these comments)
    parts.append('<div class="body"><!-- s%d-body -->\n%s\n<!-- /s%d-body --></div>'
                 % (n, blocks_html(blocks, ctx), n))
    parts.append('<div class="slot" id="s%d-slot"></div>' % n)
    notes = blocks_html(md_blocks(chunk["notes"]), ctx)
    if notes:
        parts.append('<aside class="notes">%s</aside>' % notes)
    parts.append("</section>")
    return "\n".join(parts)


THEMES = {
    "dark": dict(bg="#0F1E27", panel="#0D1820", line="#2A3D49", fg="#E6EDF0", muted="#93A7B2",
                 accent="#34D1BF", accent2="#FF8A3D", page="#05070a"),
    "light": dict(bg="#ffffff", panel="#eef1f6", line="#c4ccd8", fg="#16202e", muted="#5a6678",
                  accent="#0b6bcb", accent2="#c2410c", page="#d9dde3"),
}

CSS = """
:root{--bg:%(bg)s;--panel:%(panel)s;--line:%(line)s;--fg:%(fg)s;--muted:%(muted)s;--accent:%(accent)s;
--accent-2:%(accent2)s;--page:%(page)s;--W:%(W)dpx;--H:%(H)dpx;
--font:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
--anim-theme-bg:var(--bg);--anim-theme-panel:var(--panel);--anim-theme-line:var(--line);
--anim-theme-fg:var(--fg);--anim-theme-muted:var(--muted);--anim-theme-accent:var(--accent);
--anim-theme-accent-2:var(--accent-2);--anim-theme-font:var(--font);--anim-theme-mono:var(--mono)}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--page);color:var(--fg);font-family:var(--font)}
.deck{width:var(--W)}
.slide{position:relative;width:var(--W);height:var(--H);overflow:hidden;background:var(--bg);
display:flex;flex-direction:column;padding:%(padY)dpx %(padX)dpx;font-size:%(fs)dpx;line-height:1.35}
.slide-title{margin:0 0 .6em;font-size:1.6em;line-height:1.15;font-weight:700;color:var(--fg)}
.slide-title.lvl-1{font-size:2em}
.body{flex:0 1 auto;min-height:0;overflow:hidden}
.body>*:first-child{margin-top:0}
.body h1{font-size:1.8em;margin:.3em 0}.body h2{font-size:1.5em;margin:.3em 0}
.body h3,.body h4,.body h5,.body h6{font-size:1.2em;margin:.4em 0}
.body p{margin:0 0 .6em}.body ul,.body ol{margin:0 0 .6em;padding-left:1.4em}.body li{margin:.25em 0}
.body blockquote{margin:.3em 0 .6em;padding:.1em 0 .1em .8em;border-left:.2em solid var(--accent);color:var(--muted)}
.body blockquote p{margin:0}
.body code{font-family:var(--mono);font-size:.9em;background:var(--panel);padding:.05em .3em;border-radius:.2em}
.body pre{background:var(--panel);padding:.6em .8em;border-radius:.3em;overflow:hidden;font-size:.75em;margin:0 0 .6em}
.body pre code{background:none;padding:0;font-size:1em;white-space:pre}
.body table{border-collapse:collapse;margin:0 0 .6em;font-size:.85em}
.body th,.body td{border:1px solid var(--line);padding:.25em .6em;text-align:left}
.body th{background:var(--panel)}
.body img{max-width:100%%;max-height:%(imgH)dpx;display:block;margin:.3em 0}
.body strong{color:var(--accent)}.body del{color:var(--muted)}
.body a{color:var(--accent);text-decoration:underline}
.img-missing{display:inline-block;color:var(--muted);border:1px dashed var(--line);padding:.1em .5em;font-size:.7em}
.body:has(.anim){flex:1 1 0;display:flex;align-items:center;justify-content:center}
.body:has(.anim)>*{width:100%%;height:100%%;margin:0}
.body:has(.anim)~.slot:empty{display:none}
.slot{flex:1 1 0;min-height:0;position:relative;display:flex;align-items:center;justify-content:center}
.slot>*{width:100%%;height:100%%}
.slide.cover{justify-content:center;text-align:center}
.slide.cover .slide-title{font-size:2.4em}.slide.cover .body{color:var(--muted)}
.slide.cover .slot{flex:0 0 0}
.notes{display:none}
.counter{position:absolute;right:%(padX)dpx;bottom:28px;font-size:22px;color:var(--muted)}
/* presenting (script present): one slide at a time, scaled to the window */
html.js,html.js body{height:100%%;overflow:hidden}
html.js .deck{position:absolute;left:50%%;top:50%%;height:var(--H);transform-origin:0 0}
html.js .slide{position:absolute;left:0;top:0;display:none}
html.js .slide.current{display:flex}
@media print{
  @page{size:%(W)dpx %(H)dpx;margin:0}
  html,body,html.js,html.js body{height:auto;overflow:visible;background:var(--bg)}
  html.js .deck,.deck{position:static;transform:none !important}
  html.js .slide,.slide{position:relative;display:flex !important;break-after:page;page-break-after:always}
  .counter{display:none}
}
@media (prefers-reduced-motion:reduce){.slide{transition:none}}
"""

JS = """
(function () {
  var root = document.documentElement;
  root.classList.add('js');
  var deck = document.querySelector('.deck');
  var slides = Array.prototype.slice.call(document.querySelectorAll('.deck > section.slide'));
  var W = %(W)d, H = %(H)d, BASE_FS = %(fs)d, cur = -1;
  function fit() {
    var k = Math.min(window.innerWidth / W, window.innerHeight / H);
    deck.style.transform = 'translate(' + (-W * k / 2) + 'px,' + (-H * k / 2) + 'px) scale(' + k + ')';
  }
  function shrink(s) {  // keep long slides inside the stage
    var body = s.querySelector('.body');
    if (!body || s.dataset.fitted) return;
    s.dataset.fitted = '1';
    for (var fs = BASE_FS; fs > 18 && body.scrollHeight > body.clientHeight + 1; fs -= 2) {
      s.style.fontSize = fs + 'px';
    }
  }
  function fromHash() {
    var m = /^#s?(\\d+)$/.exec(location.hash);
    return m ? Math.min(Math.max(parseInt(m[1], 10), 1), slides.length) - 1 : 0;
  }
  // gate: the current slide's <section> carries "visible", like scripts/snippets/observer.html
  // adds it to a fragment's closest <section> while that section is on screen
  function show(i) {
    i = Math.min(Math.max(i, 0), slides.length - 1);
    if (i === cur) return;
    slides.forEach(function (s, k) {
      s.classList.toggle('current', k === i);
      s.classList.toggle('visible', k === i);
    });
    cur = i;
    shrink(slides[i]);
    var h = '#' + (i + 1);
    if (location.hash !== h && location.hash !== '#s' + (i + 1)) history.replaceState(null, '', h);
  }
  document.addEventListener('keydown', function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    var k = e.key, next = ['ArrowRight', 'ArrowDown', 'PageDown', ' ', 'Spacebar'],
        prev = ['ArrowLeft', 'ArrowUp', 'PageUp'];
    if (next.indexOf(k) >= 0) show(e.shiftKey && k === ' ' ? cur - 1 : cur + 1);
    else if (prev.indexOf(k) >= 0) show(cur - 1);
    else if (k === 'Home') show(0);
    else if (k === 'End') show(slides.length - 1);
    else return;
    e.preventDefault();
  });
  window.addEventListener('hashchange', function () { show(fromHash()); });
  window.addEventListener('resize', fit);
  // print shows every slide at rest: no gate class while printing
  window.addEventListener('beforeprint', function () {
    slides.forEach(function (s) { s.classList.remove('visible'); shrink(s); });
  });
  window.addEventListener('afterprint', function () {
    if (slides[cur]) slides[cur].classList.add('visible');
  });
  fit();
  show(fromHash());
})();
"""


def build(path, title=None, stage=(1920, 1080), theme="dark"):
    with open(path, encoding="utf-8", errors="replace") as f:
        chunks = md_chunks(f.read())
    if not chunks:
        raise SystemExit("no slides found in %s" % path)
    ctx = Ctx(os.path.dirname(os.path.abspath(path)))
    W, H = stage
    k = W / 1920
    fs = max(18, round(40 * k))
    vals = dict(THEMES[theme], W=W, H=H, padX=round(120 * k), padY=round(84 * k), fs=fs,
                imgH=round(H * 0.6))
    sections = [slide_html(i, c, ctx) for i, c in enumerate(chunks, 1)]
    total = len(sections)
    sections = [s.replace("</section>", '<div class="counter">%d / %d</div>\n</section>' % (i, total), 1)
                if s.endswith("</section>") else s for i, s in enumerate(sections, 1)]
    if not title:
        first = next((b[2] for b in md_blocks(chunks[0]["body"]) if b[0] == "heading"), "")
        title = md_inline_text(first) or os.path.splitext(os.path.basename(path))[0]
    page = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            "<title>%s</title>\n<style>%s</style>\n</head>\n<body>\n<main class=\"deck\">\n%s\n</main>\n"
            "<script>%s</script>\n</body>\n</html>\n") % (
        html.escape(title), CSS % vals, "\n".join(sections), JS % dict(W=W, H=H, fs=fs))
    if ctx.missing:
        miss = list(dict.fromkeys(ctx.missing))
        ctx.warnings.append("%d image(s) referenced by the .md are missing, shown as placeholders: %s\n"
                            "  hint: download them next to the .md (same relative paths) and re-run"
                            % (len(miss), ", ".join(miss)))
    return page, total, ctx.warnings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", help="Markdown deck (.md)")
    ap.add_argument("-o", "--output", help="output HTML (default: <source>.html next to the source)")
    ap.add_argument("--title", help="page title (default: the first heading)")
    ap.add_argument("--stage", nargs=2, type=int, metavar=("W", "H"), default=[1920, 1080])
    ap.add_argument("--theme", choices=sorted(THEMES), default="dark")
    a = ap.parse_args(argv)
    if a.stage[0] < 320 or a.stage[1] < 180:
        ap.error("--stage too small")
    page, total, warnings = build(a.source, a.title, tuple(a.stage), a.theme)
    out = a.output or os.path.splitext(a.source)[0] + ".html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    for w in dict.fromkeys(warnings):
        print("warning: " + w, file=sys.stderr)
    print("wrote %s: %d slides, stage %dx%d, theme %s; body markers '<!-- sN-body -->' ... '<!-- /sN-body -->', "
          "slot anchor 'id=\"sN-slot\">'"
          % (out, total, a.stage[0], a.stage[1], a.theme), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
