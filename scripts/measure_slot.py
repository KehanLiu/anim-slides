#!/usr/bin/env python3
"""Measure the free box of one slide in stage pixels, with headless Chrome. Standard library only.

Usage:
  measure_slot.py DECK.html --slide N|#hash|SELECTOR [--selector SEL] [--ignore SEL ...]
                  [--stage W H] [--gap PX]

  --slide     N         the Nth slide (Nth .slide element, else Nth <section>), as render-phases.sh
              #hash     open the page at that hash (#/4 reveal.js, #4 md_to_deck.py) and take the
                        current slide (section.present, .slide.current, :target)
              SELECTOR  a CSS selector for the slide element
  --selector  measure this element instead (searched inside the slide first), e.g. '#s33-slot',
              '.body' or '#slot-loan'
  --ignore    treat matching elements inside the slide as empty (repeatable), e.g. --ignore .body
              to measure the box a fragment gets when it replaces the bullets of an md_to_deck.py
              slide (--anchor '<!-- sN-body -->' --replace-until '<!-- /sN-body -->')
  --stage     browser window size (default 1920 1080); results are in the deck's own stage
              pixels whatever the window, because the slide's scale is measured and undone
  --gap       clearance kept from the title and text, in stage px (default 24)

Without --selector the free box is approximate: the slide's content box (its padding removed;
reveal.js sections shorter than the stage use the stage; with no padding, the left and top
margins of the content are mirrored to the right and bottom) minus the title and the text blocks.
Two candidates are tried, the band below all text and the column right of the body text (below
the title); the larger one wins. Text whose top lies in the bottom 12 % of the content box
(footers, page numbers) caps the bottom edge instead. Existing fragments (.anim), notes and
display:none elements are ignored; the title is the first h1/h2/h3/.slide-title/.title/header.

Output on stdout, one item per line:
  x y w h                       the box in stage pixels (origin: the stage's top-left)
  viewBox 0 0 VW VH             same aspect ratio, rounded to tens
  --rendered-width W --stage-width SW    flags for check_fragment.py / scaffold_from_spec.py
Details (which slide, which candidate, the window's display factor) go to stderr.

How: a temp copy of the page gets a <base> and a small script that measures on load and writes
JSON into <pre id="anim-measure">; Chrome's --dump-dom prints the DOM and the JSON is read back.
No virtual time budget: decks that lay out on a timer are measured as they stand at load.
Set CHROME=/path/to/chrome if it is not found.
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

JS = r"""
(function () {
  var A = __ARGS__;
  // hidden-but-laid-out text (reveal.js future slides and fragments) still takes room: only
  // display:none drops out, and it has no client rects anyway
  function vis(e) { return e.getClientRects().length > 0; }
  function run() {
    var out = {};
    try {
      var el = null, how = '';
      if (A.n) {
        var l = document.querySelectorAll('.slide');
        if (!l.length) l = document.querySelectorAll('section');
        el = l[A.n - 1] || null; how = 'slide ' + A.n + ' of ' + l.length;
      } else if (A.hash) {
        el = document.querySelector('section.present:not(.stack), .slide.current, section.current, .slide.visible, :target');
        how = 'current slide at ' + A.hash;
      } else {
        el = document.querySelector(A.sel); how = 'selector ' + A.sel;
      }
      if (!el) { out.error = 'no slide found (' + how + ')'; return done(out); }
      if (getComputedStyle(el).display === 'none') el.classList.add('current', 'present', 'visible');
      if (getComputedStyle(el).display === 'none') el.style.setProperty('display', 'block', 'important');
      var er = el.getBoundingClientRect();
      var k = el.offsetWidth ? er.width / el.offsetWidth : 1;
      var cs = getComputedStyle(el), par = el.parentElement;
      var ox = 0, oy = 0, stage = [el.offsetWidth, el.offsetHeight];
      // reveal.js: a section can be shorter than the stage (.slides); measure against the stage
      if (par && par.offsetHeight && el.offsetHeight < 0.75 * par.offsetHeight &&
          Math.abs(par.offsetWidth - el.offsetWidth) < 4 && el.offsetParent === par) {
        ox = el.offsetLeft; oy = el.offsetTop; stage = [par.offsetWidth, par.offsetHeight];
        out.container = 'stage (' + (par.className || par.tagName.toLowerCase()) + ')';
      } else out.container = 'slide';
      function box(r) {  // client rect -> stage px
        return [(r.left - er.left) / k + ox, (r.top - er.top) / k + oy,
                (r.right - er.left) / k + ox, (r.bottom - er.top) / k + oy];
      }
      var pl = parseFloat(cs.paddingLeft) || 0, pr = parseFloat(cs.paddingRight) || 0,
          pt = parseFloat(cs.paddingTop) || 0, pb = parseFloat(cs.paddingBottom) || 0;
      var C = out.container === 'slide' ? [pl, pt, stage[0] - pr, stage[1] - pb]
                                        : [pl, Math.max(0, oy) + pt, stage[0] - pr, stage[1] - pb];
      out.desc = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + ' (' + how + ')';
      out.stage = stage; out.scale = k; out.content = C;
      if (A.target) {
        var t = el.querySelector(A.target) || document.querySelector(A.target);
        if (!t) { out.error = 'no element matches --selector ' + A.target; return done(out); }
        out.box = box(t.getBoundingClientRect()); out.how = 'bounding box of ' + A.target;
        return done(out);
      }
      var ignore = [];
      A.ignore.forEach(function (s) { el.querySelectorAll(s).forEach(function (x) { ignore.push(x); }); });
      function skipped(e) {
        for (; e && e !== el; e = e.parentElement) {
          if (ignore.indexOf(e) >= 0 || e.id === 'anim-measure') return true;
          if (e.matches && e.matches('.anim, aside.notes, .notes, script, style, template')) return true;
        }
        return false;
      }
      var title = null;
      var heads = el.querySelectorAll('h1, h2, h3, .slide-title, .title, header');
      for (var i = 0; i < heads.length && !title; i++)
        if (!skipped(heads[i]) && vis(heads[i]) && heads[i].textContent.trim()) title = heads[i];
      var rects = [];  // {b: box, title: bool, float: bool}
      function add(r, node) {
        if (r.width < 1 || r.height < 1) return;
        rects.push({b: box(r), title: !!(title && title.contains(node))});
      }
      var w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null), tn;
      while ((tn = w.nextNode())) {
        var p = tn.parentElement;
        if (!tn.nodeValue.trim() || skipped(p) || !vis(p)) continue;
        var rg = document.createRange(); rg.selectNodeContents(tn);
        Array.prototype.forEach.call(rg.getClientRects(), function (r) { add(r, p); });
      }
      el.querySelectorAll('img, svg, video, canvas, iframe, object, embed, table, pre, .img-missing').forEach(function (e) {
        if (skipped(e) || !vis(e) || (e.tagName.toLowerCase() === 'svg' && e.parentElement.closest('svg'))) return;
        add(e.getBoundingClientRect(), e);
      });
      // no padding on the slide (reveal.js): mirror the margin the content keeps on the left and
      // at the top, so the box keeps the deck's own margins
      if (rects.length && pl < 1 && pr < 1) {
        var ml = Infinity;
        rects.forEach(function (o) { ml = Math.min(ml, o.b[0] - C[0]); });
        if (ml > 0 && ml < (C[2] - C[0]) / 4) { C[0] += ml; C[2] -= ml; }
      }
      if (rects.length && pt < 1 && pb < 1) {
        var mt = Infinity;
        rects.forEach(function (o) { mt = Math.min(mt, o.b[1] - C[1]); });
        if (mt > 0 && mt < (C[3] - C[1]) / 5) C[3] -= mt;
      }
      out.content = C;
      // footer zone: small text whose top lies in the bottom 12 % (page numbers, sources)
      var G = A.gap, footY = C[3] - 0.12 * (C[3] - C[1]);
      var tb = C[1], bot = C[3];
      rects.forEach(function (o) {
        o.foot = !o.title && o.b[1] >= footY;
        if (o.title) tb = Math.max(tb, o.b[3] + G);
        else if (o.foot) bot = Math.min(bot, o.b[1] - G);
      });
      out.rects = rects.length;
      var body = rects.filter(function (o) { return !o.title && !o.foot; });
      var cands = [];
      var below = tb;
      body.forEach(function (o) { below = Math.max(below, o.b[3] + G); });
      cands.push({how: body.length ? 'below the text' : (title ? 'below the title' : 'the whole content box'),
                  box: [C[0], below, C[2], bot]});
      if (body.length) {
        var right = C[0];
        body.forEach(function (o) { right = Math.max(right, o.b[2] + G); });
        cands.push({how: 'right of the body text, below the title', box: [right, tb, C[2], bot]});
      }
      cands.forEach(function (c) { c.area = Math.max(0, c.box[2] - c.box[0]) * Math.max(0, c.box[3] - c.box[1]); });
      cands.sort(function (a, b) { return b.area - a.area; });
      out.box = cands[0].box; out.how = cands[0].how; out.others = cands.slice(1);
    } catch (e) { out.error = String(e && e.stack || e); }
    done(out);
  }
  function done(out) {
    var pre = document.createElement('pre');
    pre.id = 'anim-measure';
    pre.textContent = JSON.stringify(out);
    document.body.appendChild(pre);
  }
  if (document.readyState === 'complete') run(); else window.addEventListener('load', run);
})();
"""


def find_chrome():
    env = os.environ.get('CHROME')
    if env:
        return env if (os.path.isfile(env) or shutil.which(env)) else None
    for c in ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
              '/Applications/Chromium.app/Contents/MacOS/Chromium',
              '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
              os.path.expanduser('~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')):
        if os.access(c, os.X_OK):
            return c
    for c in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'microsoft-edge',
              'chrome', 'msedge'):
        if shutil.which(c):
            return shutil.which(c)
    return None


def r10(v):
    return max(10, int(round(v / 10.0)) * 10)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('page')
    ap.add_argument('--slide', required=True, help='N, #hash or a CSS selector for the slide')
    ap.add_argument('--selector', help='measure this element instead of the free box')
    ap.add_argument('--ignore', action='append', default=[], help='treat these elements as empty')
    ap.add_argument('--stage', nargs=2, type=int, default=[1920, 1080], metavar=('W', 'H'))
    ap.add_argument('--gap', type=float, default=24)
    ap.add_argument('--timeout', type=int, default=60, help='seconds to wait for Chrome (default 60)')
    a = ap.parse_args()
    if not os.path.isfile(a.page):
        sys.exit(f'measure_slot: {a.page}: not found')
    chrome = find_chrome()
    if not chrome:
        sys.exit('measure_slot: no Chrome/Chromium/Edge found; set CHROME=/path/to/chrome')

    s, hash_ = a.slide.strip(), ''
    args = dict(n=0, hash='', sel='', target=a.selector or '', ignore=a.ignore, gap=a.gap)
    if s.isdigit():
        if int(s) < 1:
            sys.exit('measure_slot: --slide N starts at 1')
        args['n'] = int(s)
    elif s.startswith('#'):
        if not re.match(r'^#[A-Za-z0-9/_.:-]*$', s):
            sys.exit('measure_slot: --slide #hash: letters, digits and / _ . : - only')
        hash_ = args['hash'] = s
    else:
        args['sel'] = s

    src = os.path.abspath(a.page)
    raw = open(src, encoding='utf-8', errors='replace').read()
    from urllib.parse import quote
    base = '<base href="file://%s/">' % quote(os.path.dirname(src))
    m = re.search(r'<head\b[^>]*>', raw, re.I)
    raw = raw[:m.end()] + base + raw[m.end():] if m else base + raw
    js = '<script>' + JS.replace('__ARGS__', json.dumps(args).replace('</', '<\\/')) + '</script>'
    ends = list(re.finditer(r'</body\s*>', raw, re.I))
    raw = raw[:ends[-1].start()] + js + raw[ends[-1].start():] if ends else raw + js

    tmp = tempfile.mkdtemp(prefix='measure-slot-')
    try:
        tmp_page = os.path.join(tmp, 'measure.html')
        with open(tmp_page, 'w', encoding='utf-8') as f:
            f.write(raw)
        cmd = [chrome, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
               '--window-size=%d,%d' % tuple(a.stage), '--dump-dom', 'file://' + quote(tmp_page) + hash_]
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=a.timeout)
        except subprocess.TimeoutExpired:
            sys.exit(f'measure_slot: Chrome did not finish within {a.timeout} s')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    dom = p.stdout.decode('utf-8', 'replace')
    mm = re.search(r'<pre id="anim-measure">(.*?)</pre>', dom, re.S)
    if not mm:
        sys.exit('measure_slot: no measurement in the dumped DOM (the page script failed or the page did not load)')
    res = json.loads(html.unescape(mm.group(1)))
    if res.get('error'):
        sys.exit('measure_slot: ' + res['error'])

    x0, y0, x1, y1 = res['box']
    x, y, w, h = round(x0), round(y0), round(x1 - x0), round(y1 - y0)
    sw, sh = res['stage']
    k = res['scale']  # how the deck letterboxes the stage into the browser window; undone above
    shown = '' if abs(k - 1) < 0.0005 else \
        f' (the window shows it at {round(sw * k)} px wide, factor {k:.3f}; results are in stage px)'
    print(f'{res["desc"]}: stage {sw}x{sh}{shown}, measured against the {res["container"]}',
          file=sys.stderr)
    print(f'box: {res["how"]}', file=sys.stderr)
    for o in res.get('others', []):
        b = o['box']
        print(f'  other candidate, {o["how"]}: {round(b[0])} {round(b[1])} {round(b[2] - b[0])} {round(b[3] - b[1])}',
              file=sys.stderr)
    if w < 40 or h < 40:
        print(f'warning: the box is {w} x {h}; the slide has no room (try --ignore, --selector or a layout '
              'from references/layouts.md)', file=sys.stderr)
        w, h = max(w, 0), max(h, 0)
    print(f'{x} {y} {w} {h}')
    print(f'viewBox 0 0 {r10(w)} {r10(h)}')
    print(f'--rendered-width {w} --stage-width {sw}')


if __name__ == '__main__':
    main()
