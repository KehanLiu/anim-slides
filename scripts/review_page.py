#!/usr/bin/env python3
"""Write a self-contained before/after review page for a deck run ("show, don't tell"). Stdlib only.

Usage:
  review_page.py --deck deck.html --before DIR --after DIR [--triage anim/triage.md]
                 -o anim/review/index.html [--title TEXT] [--stage W H] [--only animated]
                 [--previous DIR] [--link-images] [--no-live]

  --before DIR   PNGs of the source slides, one per slide. The slide number is the first integer
                 in the file name (p-07.png, slide-7.png, s07.png) or in a folder name (s7/, s07/,
                 slide-7/ holding phase-rest.png or a single PNG). render_deck.py's OUTDIR works
                 as is: full/ is used first, pages/ fills the gaps, contact sheets are skipped.
                 Folders with other names (bundled-s3, s27-mid) are ignored.
  --after DIR    the same for the integrated deck's resting-frame renders
                 (render-phases.sh --page deck.html --slide N ... rest -> sN/phase-rest.png).
  --previous DIR an earlier attempt, shown as a middle column.
  --triage FILE  anim/triage.md: header lines (Look:, Control:, Host deck:, Source:) go to the
                 intro; the table (Slide | Title | Decision | Archetype | Replaces | Why) goes
                 under each pair.
  --only animated  only slides whose triage decision is illustrate or whose deck slide holds a
                 data-anim fragment. Default: every slide that has a before image.
  --stage W H    slide aspect for the image boxes (default 1920 1080).
  --link-images  reference the PNGs by relative path instead of embedding them as data: URIs.
  --no-live      stills only (the page before live figures).

Live figures: for every slide whose --deck slide holds a data-anim fragment, the after column
shows the fragment itself, taken from the deck (between its anim:NAME / anim-style:NAME markers,
or by its div.anim.anim-NAME wrapper and the .anim-NAME rules), on the slide's ground with the
deck's --anim-theme-* values (deck CSS first, anim/host-theme.css next to the deck fills gaps).
It plays one pass when it scrolls into view and has a Replay button; a step-mode fragment plays
through. The resting-frame still stays below it, smaller; print shows the still only, and
prefers-reduced-motion shows the fragment's resting frame. A slide whose fragment cannot be
extracted keeps the still (WARN line).

The page has no external loads; with embedded images the one file travels on its own.
Exit: 0 ok, 1 nothing to show or unreadable input, 2 bad arguments.
"""
import argparse
import base64
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_slides import TreeBuilder, leaf_containers, node_text, collapse  # noqa: E402
from host_theme import TOKENS  # noqa: E402
from build_gallery import viewbox_of  # noqa: E402

SKIP = re.compile(r'^(sheet|contact|thumb)', re.I)
FOLDER = re.compile(r'(?:s|slide|p|page)?[-_]?0*(\d+)', re.I)
HEAD_KEYS = ('Look', 'Control', 'Host deck', 'Source')


def first_int(name):
    m = re.search(r'\d+', name)
    return int(m.group(0)) if m else None


def collect(d):
    """{slide number: png path} for one render folder."""
    if not d:
        return {}
    if not os.path.isdir(d):
        sys.exit(f'review_page: not a folder: {d}')
    out = {}
    subs = [os.path.join(d, x) for x in ('full', 'pages') if os.path.isdir(os.path.join(d, x))]
    for folder in subs + [d]:
        for f in sorted(os.listdir(folder)):
            p = os.path.join(folder, f)
            if os.path.isfile(p) and f.lower().endswith('.png') and not SKIP.match(f):
                n = first_int(f)
                if n is not None:
                    out.setdefault(n, p)
    for f in sorted(os.listdir(d)):
        p, m = os.path.join(d, f), FOLDER.fullmatch(f)
        if not (os.path.isdir(p) and m) or f in ('full', 'pages'):
            continue
        pngs = sorted(x for x in os.listdir(p) if x.lower().endswith('.png') and not SKIP.match(x))
        pick = next((x for x in pngs if x.lower() == 'phase-rest.png'), None) or \
            next((x for x in pngs if 'rest' in x.lower()), None) or (pngs[0] if len(pngs) == 1 else None)
        if pick:
            out.setdefault(int(m.group(1)), os.path.join(p, pick))
    return out


def read_triage(path):
    head, rows = {}, {}
    if not path:
        return head, rows
    try:
        lines = open(path, encoding='utf-8').read().splitlines()
    except OSError as e:
        sys.exit(f'review_page: cannot read {path}: {e}')
    cols = None
    for ln in lines:
        m = re.match(r'\s*(' + '|'.join(HEAD_KEYS) + r')\s*:\s*(.+)$', ln, re.I)
        if m and not ln.lstrip().startswith('|'):
            key = next(k for k in HEAD_KEYS if k.lower() == m.group(1).lower())
            head.setdefault(key, m.group(2).strip())
            continue
        if not ln.strip().startswith('|'):
            cols = None if ln.strip() else cols
            continue
        cells = [c.strip() for c in ln.strip().strip('|').split('|')]
        if cols is None:
            if any(c.lower() == 'slide' for c in cells):
                cols = [c.lower() for c in cells]
            continue
        if all(re.fullmatch(r':?-+:?', c) for c in cells if c):
            continue
        row = dict(zip(cols, cells))
        n = first_int(row.get('slide', ''))
        if n is not None:
            rows[n] = row
    return head, rows


def final_decision(d):
    return re.split(r'->|→', d or '')[-1].strip().lower()


def read_deck(path):
    """(slides, html root node, source) with one dict per slide container, in order:
    title, anim (holds data-anim), names (fragment names), node (the slide element)."""
    if not path:
        return [], None, ''
    tb = TreeBuilder()
    try:
        src = open(path, encoding='utf-8', errors='replace').read()
    except OSError as e:
        sys.exit(f'review_page: cannot read {path}: {e}')
    tb.feed(src)
    tb.close()
    out = []
    for n in leaf_containers(tb.root):
        nodes = list(n.iter())
        h = next((d for d in nodes if d.tag in ('h1', 'h2')), None) or next((d for d in nodes if d.tag == 'h3'), None)
        names = []
        for d in nodes:
            if 'data-anim' not in d.attrs:
                continue
            nm = (d.attrs.get('data-anim') or '').strip()
            if not nm:
                nm = next((c[5:] for c in d.classes if c.startswith('anim-')), '')
            if nm and nm not in names:
                names.append(nm)
        out.append({'title': collapse(node_text(h)) if h is not None else '',
                    'anim': any('data-anim' in d.attrs for d in nodes), 'names': names, 'node': n})
    root = next((d for d in tb.root.iter() if d.tag == 'html'), None)
    return out, root, src


# --------------------------------------------------------------------------- live fragments
STATE = {'active', 'visible', 'present', 'current'}   # classes a deck puts on the current slide


def strip_comments(css):
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def top_blocks(css):
    """[(prelude, body)] for the top-level blocks of a CSS text (brace matching)."""
    out, depth, start, pre = [], 0, 0, 0
    for i, ch in enumerate(css):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}' and depth:
            depth -= 1
            if depth == 0:
                out.append((css[pre:start].split(';')[-1].strip(), css[start + 1:i]))
                pre = i + 1
    return out


def flat_rules(css):
    """[(selectors, [(prop, value)])] for every style rule; @media wrappers fall away except
    print (a print rule is not the screen look). Keyframes and other at-rules are skipped."""
    out = []
    for pre, body in top_blocks(css):
        if pre.startswith('@'):
            if re.match(r'@(media|supports)\b', pre) and not re.search(r'\bprint\b', pre):
                out += flat_rules(body)
            continue
        decls = []
        for d in body.split(';'):
            if ':' in d:
                p, v = d.split(':', 1)
                decls.append((p.strip().lower(), v.replace('!important', '').strip()))
        out.append(([s.strip() for s in pre.split(',') if s.strip()], decls))
    return out


def sel_matches(sel, node):
    """True when a compound selector (tag, .class, #id, [attr], [attr=v], :root) matches node.
    A slide's state classes (active, visible, ...) count as present."""
    if node is None:
        return False
    toks = re.findall(r'(:root|\*|[a-zA-Z][\w-]*|\.[\w-]+|#[\w-]+|\[[^\]]+\])', sel)
    if not toks or ''.join(toks) != sel.replace(' ', '') or ' ' in sel.strip():
        return False
    cls = set(node.classes) | (STATE if node.tag != 'html' else set())
    for t in toks:
        if t == ':root':
            ok = node.tag == 'html'
        elif t == '*':
            ok = True
        elif t[0] == '.':
            ok = t[1:].lower() in cls
        elif t[0] == '#':
            ok = node.attrs.get('id') == t[1:]
        elif t[0] == '[':
            m = re.fullmatch(r'\[\s*([\w-]+)\s*(?:([~|^$*]?=)\s*["\']?([^"\']*)["\']?)?\s*\]', t)
            if not m:
                return False
            v = node.attrs.get(m.group(1))
            ok = v is not None and (m.group(2) is None or
                                    (m.group(2) == '=' and v == m.group(3)) or
                                    (m.group(2) == '~=' and m.group(3) in v.split()))
        else:
            ok = node.tag == t.lower()
        if not ok:
            return False
    return True


def resolve(v, env, depth=0):
    if depth > 10 or 'var(' not in v:
        return v

    def sub(m):
        name, fb = m.group(1), m.group(2)
        return resolve(env[name], env, depth + 1) if name in env else resolve(fb or '', env, depth + 1)
    return resolve(re.sub(r'var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*(?:\([^()]*\)[^()]*)*))?\)', sub, v),
                   env, depth + 1)


def deck_css(src, deck_path):
    """The deck's own CSS: inline <style> blocks without the fragments' anim-style blocks, plus
    local <link rel=stylesheet> files next to it (never the network)."""
    s = re.sub(r'<!--\s*anim-style:[\w-]+:start\s*-->.*?<!--\s*anim-style:[\w-]+:end\s*-->', '', src, flags=re.S)
    css = re.findall(r'<style\b[^>]*>(.*?)</style\s*>', s, re.S | re.I)
    base = os.path.dirname(os.path.abspath(deck_path))
    for tag in re.findall(r'<link\b[^>]*>', s, re.I):
        m = re.search(r'href\s*=\s*["\']([^"\']+)["\']', tag, re.I)
        if not (re.search(r'rel\s*=\s*["\']?stylesheet', tag, re.I) and m) or \
                re.match(r'[a-z][a-z0-9+.-]*:|//', m.group(1), re.I):
            continue
        p = os.path.normpath(os.path.join(base, m.group(1).split('?')[0].split('#')[0]))
        if os.path.isfile(p):
            css.append(open(p, encoding='utf-8', errors='replace').read())
    return strip_comments('\n'.join(css))


def slide_look(slide, root, css, host_css):
    """({--anim-theme-*: value}, ground) for one slide: custom properties on the root element,
    then on rules matching the slide, then its style=""; host-theme.css fills tokens the deck
    leaves out. The ground is the slide's background (else --anim-theme-bg)."""
    def scan(rules, env, ground):
        for node in (root, slide):
            for sels, decls in rules:
                if any(sel_matches(x, node) for x in sels):
                    for p, v in decls:
                        if p.startswith('--'):
                            env[p] = v
                        elif node is slide and p in ('background', 'background-color') and v:
                            ground[0] = v
        return env, ground
    env, ground = scan(flat_rules(css), {}, [None])
    for d in (slide.attrs.get('style') or '').split(';'):
        if ':' in d:
            p, v = (x.strip() for x in d.split(':', 1))
            if p.startswith('--'):
                env[p] = v
            elif p.lower() in ('background', 'background-color'):
                ground[0] = v
    if host_css:
        henv, hground = scan(flat_rules(host_css), {}, [None])
        for k, v in henv.items():
            env.setdefault(k, v)
        ground[0] = ground[0] or hground[0]
    tokens = {}
    for k in TOKENS:
        v = env.get(f'--anim-theme-{k}')
        if v:
            v = resolve(v, env).strip()
            if v and 'url(' not in v:
                tokens[f'--anim-theme-{k}'] = v
    g = resolve(ground[0], env).strip() if ground[0] else ''
    if not g or g in ('none', 'transparent', 'inherit', 'initial') or re.search(r'url\((?!\s*["\']?data:)', g):
        g = tokens.get('--anim-theme-bg', '#0F1E27')
    return tokens, g


def pick_css(css, name):
    """The rules of one fragment in a larger CSS text (no anim-style markers)."""
    out, sel = [], re.compile(r'\.anim-' + re.escape(name) + r'(?![\w-])')
    for pre, body in top_blocks(css):
        if re.match(r'@(-webkit-)?keyframes\b', pre):
            k = pre.split()[1] if len(pre.split()) > 1 else ''
            if k == name or k.startswith(name + '-'):
                out.append(f'{pre}{{{body}}}')
        elif re.match(r'@(media|supports)\b', pre):
            inner = pick_css(body, name)
            if inner:
                out.append(f'{pre}{{{inner}}}')
        elif not pre.startswith('@') and sel.search(pre):
            out.append(f'{pre}{{{body}}}')
    return '\n'.join(out)


def wrapper_div(src, name):
    """The <div class="anim anim-NAME" ...>...</div> element in src, by div balance."""
    m = re.search(r'<div\b[^>]*\bclass\s*=\s*["\'][^"\']*\banim-' + re.escape(name) + r'(?![\w-])[^>]*>', src)
    if not m:
        return None
    depth = 0
    for t in re.finditer(r'<(/?)div\b[^>]*>', src[m.start():], re.I):
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return src[m.start():m.start() + t.end()]
    return None


def regate(css, name):
    """Rewrite the fragment's gate (the ancestor before .anim-NAME, e.g. section.present or
    .slide.visible) to .visible, the class this page toggles. Returns (css, gate or None)."""
    pat = re.compile(r'(^|[,{}])(\s*)([^,{}@]*?\S)\s+(?=\.anim-' + re.escape(name) + r'(?![\w-]))')
    seen = {}
    for m in pat.finditer(css):
        g = m.group(3).strip()
        if not re.match(r'html\.(print-pdf|reveal-print)\b', g):
            seen[g] = seen.get(g, 0) + 1
    if not seen:
        return css, None
    gate = max(seen, key=seen.get)
    if gate != '.visible':
        css = pat.sub(lambda m: m.group(1) + m.group(2) + ('.visible ' if m.group(3).strip() == gate
                                                           else m.group(3) + ' '), css)
    return css, gate


def extract_fragment(src, name):
    """(css, markup, info) for fragment NAME from the deck source, or raise ValueError."""
    body = re.search(r'<!--\s*anim:' + re.escape(name) + r':start\s*-->(.*?)<!--\s*anim:'
                     + re.escape(name) + r':end\s*-->', src, re.S)
    markup = wrapper_div(body.group(1) if body else src, name)
    if not markup or '<svg' not in markup.lower():
        raise ValueError(f'no div.anim.anim-{name} with an <svg> found')
    markup = re.sub(r'<!--.*?-->', '', markup, flags=re.S)
    markup = re.sub(r'<script\b.*?</script\s*>', '', markup, flags=re.S | re.I)
    st = re.search(r'<!--\s*anim-style:' + re.escape(name) + r':start\s*-->(.*?)<!--\s*anim-style:'
                   + re.escape(name) + r':end\s*-->', src, re.S)
    if st:
        css = strip_comments('\n'.join(re.findall(r'<style\b[^>]*>(.*?)</style\s*>', st.group(1), re.S | re.I)))
    else:
        css = pick_css(strip_comments('\n'.join(re.findall(r'<style\b[^>]*>(.*?)</style\s*>', src, re.S | re.I))), name)
    if not css.strip():
        raise ValueError(f'no CSS for .anim-{name} found')
    if re.search(r'url\(\s*["\']?(?!#|data:)[^)\s]', css) or re.search(r'\b(?:href|src)\s*=\s*["\'](?!#)', markup):
        raise ValueError('it references external files')
    css, gate = regate(css, name)
    ctl = re.search(r'\bdata-anim-control\s*=\s*["\'](\w+)', markup)
    return css, markup, {'gate': gate, 'control': ctl.group(1) if ctl else 'once',
                         'viewbox': viewbox_of(markup)}


def img_src(path, out_dir, link):
    if link:
        return os.path.relpath(path, out_dir).replace(os.sep, '/')
    with open(path, 'rb') as f:
        return 'data:image/png;base64,' + base64.b64encode(f.read()).decode('ascii')


CSS = '''
:root{--bg:#F5F6F8;--fg:#1D232A;--muted:#5B6672;--line:#D8DDE3;--box:#FFFFFF;--accent:#1F6FB2}
@media (prefers-color-scheme:dark){:root{--bg:#15191E;--fg:#E4E8EC;--muted:#98A3AE;--line:#2D343C;--box:#0E1114;--accent:#6CB4EE}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header,section,footer{max-width:1500px;margin:0 auto;padding:20px 32px}
h1{margin:8px 0 6px;font-size:26px}
.meta{margin:0;color:var(--muted);font-size:14px}.meta b{color:var(--fg);font-weight:600}
section{border-top:1px solid var(--line)}
h2{margin:0 0 10px;font-size:18px;display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}
h2 .n{font-family:ui-monospace,Menlo,monospace;color:var(--muted)}
h2 .tag{font-size:12px;font-weight:600;color:var(--accent);text-transform:uppercase;letter-spacing:.06em}
.row{display:grid;grid-template-columns:repeat(var(--cols),minmax(0,1fr));gap:16px}
figure{margin:0}
.box{aspect-ratio:var(--ar);width:100%;background:var(--box);border:1px solid var(--line);display:flex;
 align-items:center;justify-content:center;color:var(--muted);font-size:14px}
.box img{width:100%;height:100%;object-fit:contain;display:block}
figure.after.anim .box{border:2px solid var(--accent)}
figcaption{margin-top:6px;font-size:13px;color:var(--muted)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:2px 14px;margin:12px 0 0;font-size:14px}
dt{color:var(--muted)}dd{margin:0}
footer{color:var(--muted);font-size:13px;border-top:1px solid var(--line)}
.live{border:2px solid var(--accent);padding:3%;margin-bottom:8px}
.live>.fit{width:100%;margin:0 auto}
.livebar{display:flex;align-items:center;gap:12px;font-size:13px;color:var(--muted);margin:0 0 10px}
.livebar button{font:inherit;font-size:13px;font-weight:600;color:var(--fg);background:var(--box);
 border:1px solid var(--line);border-radius:6px;padding:3px 12px;cursor:pointer}
.livebar button:hover{border-color:var(--accent)}
.rest{width:46%}
.rest .box{border-width:1px}
@media (max-width:820px){.row{grid-template-columns:1fr}header,section,footer{padding:16px}}
@media print{.live,.livebar{display:none}.rest{width:100%}}
'''

# Live figures: a figure plays one pass the first time it scrolls into view and keeps the gate,
# so it rests on its finished frame; Replay drops the gate, forces a reflow and sets it again
# (the gallery's technique). Restarting the animations from 0 also covers an ungated fragment.
JS = '''
(function(){
  function restart(l){if(l.getAnimations)l.getAnimations({subtree:true}).forEach(function(a){
    try{a.currentTime=0;a.play()}catch(e){}})}
  function play(f){if(!f)return;f._played=true;f.querySelectorAll('.live').forEach(function(l){
    l.classList.remove('visible');void l.offsetWidth;l.classList.add('visible');restart(l)})}
  document.addEventListener('click',function(ev){var b=ev.target.closest('[data-replay]');
    if(b)play(document.getElementById(b.getAttribute('data-replay')))});
  var figs=document.querySelectorAll('figure.livefig');
  if(!('IntersectionObserver' in window)){figs.forEach(play);return}
  var io=new IntersectionObserver(function(es){es.forEach(function(e){var f=e.target.closest('figure');
    if(e.isIntersecting&&!f._played){play(f);io.unobserve(e.target)}})},{threshold:0.5});
  figs.forEach(function(f){var l=f.querySelector('.live');if(l)io.observe(l)});
})();
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split('\n', 2)[2])
    ap.add_argument('--deck', help='the integrated deck (slide titles, data-anim detection)')
    ap.add_argument('--before', required=True, metavar='DIR')
    ap.add_argument('--after', required=True, metavar='DIR')
    ap.add_argument('--previous', metavar='DIR')
    ap.add_argument('--triage', metavar='FILE')
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--title')
    ap.add_argument('--stage', nargs=2, type=int, metavar=('W', 'H'), default=[1920, 1080])
    ap.add_argument('--only', choices=['animated'])
    ap.add_argument('--link-images', action='store_true')
    ap.add_argument('--no-live', action='store_true', help='stills only, no live figures')
    a = ap.parse_args()
    if min(a.stage) <= 0:
        ap.error('--stage W H must be positive')

    before, after, prev = collect(a.before), collect(a.after), collect(a.previous)
    head, triage = read_triage(a.triage)
    deck, deck_root, deck_src = read_deck(a.deck)
    in_deck = {i for i, s in enumerate(deck, 1) if s['anim']}
    in_triage = {n for n, r in triage.items() if final_decision(r.get('decision')) == 'illustrate'}
    if deck and triage:
        for n in sorted(in_triage - in_deck):
            print(f'review_page: WARN triage says illustrate for slide {n}, the deck has no data-anim there',
                  file=sys.stderr)
        for n in sorted(in_deck - in_triage):
            print(f'review_page: WARN deck slide {n} holds a data-anim fragment, triage does not say illustrate',
                  file=sys.stderr)
    animated = in_deck | in_triage
    total = len(deck) or max([len(triage)] + list(triage) + list(before)) or 0
    shown = sorted(n for n in before if a.only != 'animated' or n in animated)
    if not shown:
        print('review_page: nothing to show (no before images' + (' for animated slides' if a.only else '')
              + f' in {a.before})', file=sys.stderr)
        return 1

    out_dir = os.path.dirname(os.path.abspath(a.output))
    deck_name = os.path.basename(a.deck) if a.deck else head.get('Host deck', 'deck')
    title = a.title or f'{deck_name}: before and after'
    cols = 3 if a.previous else 2
    e = html.escape

    # live figures: one per fragment on each shown slide that holds one
    live, live_css, fallback = {}, [], []
    if a.deck and not a.no_live:
        css = deck_css(deck_src, a.deck)
        hp = os.path.join(os.path.dirname(os.path.abspath(a.deck)), 'anim', 'host-theme.css')
        host_css = strip_comments(open(hp, encoding='utf-8', errors='replace').read()) if os.path.isfile(hp) else ''
        done = set()
        for n in shown:
            s = deck[n - 1] if n <= len(deck) else None
            if not s or not s['names']:
                continue
            tokens, ground = slide_look(s['node'], deck_root, css, host_css)
            boxes = []
            try:
                for nm in s['names']:
                    if nm in done:
                        raise ValueError(f'fragment {nm} already shown on an earlier slide')
                    fcss, markup, info = extract_fragment(deck_src, nm)
                    boxes.append((nm, fcss, markup, info))
            except ValueError as err:
                print(f'review_page: WARN slide {n}: live figure not embedded ({err}); showing the still',
                      file=sys.stderr)
                fallback.append(n)
                continue
            for nm, fcss, markup, info in boxes:
                done.add(nm)
                live_css.append(f'/* fragment {nm}, slide {n} */\n{fcss}')
            style = ';'.join(f'{k}:{v}' for k, v in tokens.items())
            style += f';background:{ground};color:{tokens.get("--anim-theme-fg", "#E6EDF0")}'
            if '--anim-theme-font' in tokens:
                style += f';font-family:{tokens["--anim-theme-font"]}'
            live[n] = (style, boxes)

    meta = [f'<b>{e(k)}:</b> {e(head[k])}' for k in HEAD_KEYS if k in head]
    meta.append(f'<b>{len(animated)} of {total}</b> slides animated; showing {len(shown)} '
                f'slide{"s" if len(shown) != 1 else ""}' + (' (animated only)' if a.only else '')
                + ('. Animated slides play live, once, when they scroll into view (Replay plays them again);'
                   ' the small still under each is the resting frame, the state a PDF export shows.' if live else
                   '. Animated slides show the resting frame, the state a PDF export shows.'))
    parts = [f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
             f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title>'
             f'<style>{CSS}:root{{--cols:{cols};--ar:{a.stage[0]}/{a.stage[1]}}}</style>'
             + (f'<style>\n{chr(10).join(live_css)}\n</style>' if live_css else '') + '</head><body>'
             f'<header><h1>{e(title)}</h1>' + ''.join(f'<p class="meta">{m}</p>' for m in meta) + '</header>']

    def fig(cls, src, cap, n):
        inner = (f'<img src="{e(img_src(src, out_dir, a.link_images))}" alt="{e(cap)}, slide {n}" loading="lazy">'
                 if src else 'no render')
        return f'<figure class="{cls}"><div class="box">{inner}</div><figcaption>{e(cap)}</figcaption></figure>'

    def live_fig(n, src):
        style, boxes = live[n]
        out = []
        for nm, _, markup, info in boxes:
            w, h = info['viewbox']
            out.append(f'<div class="live" style="{e(style)}" data-fragment="{e(nm)}">'
                       f'<div class="fit" style="aspect-ratio:{w:g}/{h:g}">{markup}</div></div>')
        step = any(i['control'] == 'step' for _, _, _, i in boxes)
        note = ('Live: plays once when it scrolls into view'
                + (' (step deck: the presenter clicks through it; here it plays through)' if step else ''))
        rest = (f'<img src="{e(img_src(src, out_dir, a.link_images))}" alt="Resting frame, slide {n}" loading="lazy">'
                if src else 'no render')
        return (f'<figure class="after anim livefig" id="fig-{n}">{"".join(out)}'
                f'<div class="livebar"><button type="button" data-replay="fig-{n}">Replay</button>'
                f'<span>{e(note)}</span></div>'
                f'<div class="rest"><div class="box">{rest}</div>'
                f'<figcaption>Resting frame (full slide, as in a PDF)</figcaption></div></figure>')

    missing = []
    for n in shown:
        row = triage.get(n, {})
        name = row.get('title') or (deck[n - 1]['title'] if n <= len(deck) else '') or f'Slide {n}'
        anim = n in animated
        if n not in after:
            missing.append(n)
        figs = [fig('before', before[n], 'Original', n)]
        if a.previous:
            figs.append(fig('prev', prev.get(n), 'Previous attempt', n))
        if n in live:
            figs.append(live_fig(n, after.get(n)))
        else:
            figs.append(fig('after anim' if anim else 'after', after.get(n),
                            'Animated (resting frame)' if anim else 'Deck', n))
        dl = ''.join(f'<dt>{k.title()}</dt><dd>{e(row[k])}</dd>' for k in
                     ('decision', 'archetype', 'replaces', 'why') if row.get(k) and row[k] != '-')
        parts.append(f'<section><h2><span class="n">{n}</span>{e(name)}'
                     + ('<span class="tag">animated</span>' if anim else '') + '</h2>'
                     f'<div class="row">{"".join(figs)}</div>' + (f'<dl>{dl}</dl>' if dl else '') + '</section>')
    parts.append('<footer>generated by anim-slides review_page.py</footer>'
                 + (f'<script>{JS}</script>' if live else '') + '</body></html>\n')
    os.makedirs(out_dir, exist_ok=True)
    with open(a.output, 'w', encoding='utf-8') as f:
        f.write(''.join(parts))
    if missing:
        lst = ', '.join(map(str, missing[:10])) + (f' ... ({len(missing)} in all)' if len(missing) > 10 else '')
        print(f'review_page: WARN no after render for slide(s) {lst}', file=sys.stderr)
    print(f'review_page: wrote {a.output}: {len(shown)} slide(s), {len(animated)} of {total} animated, '
          f'{cols} columns, {len(live)} live figure(s)'
          + (f' (still only: slide(s) {", ".join(map(str, fallback))})' if fallback else '')
          + f', images {"linked" if a.link_images else "embedded"} '
          f'({os.path.getsize(a.output) // 1024} KB)', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
