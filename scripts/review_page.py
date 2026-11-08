#!/usr/bin/env python3
"""Write a self-contained before/after review page for a deck run ("show, don't tell"). Stdlib only.

Usage:
  review_page.py --deck deck.html --before DIR --after DIR [--triage anim/triage.md]
                 -o anim/review/index.html [--title TEXT] [--stage W H] [--only animated]
                 [--previous DIR] [--link-images]

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
    """[(title, has data-anim)] per slide container, in order."""
    if not path:
        return []
    tb = TreeBuilder()
    try:
        tb.feed(open(path, encoding='utf-8', errors='replace').read())
    except OSError as e:
        sys.exit(f'review_page: cannot read {path}: {e}')
    tb.close()
    out = []
    for n in leaf_containers(tb.root):
        nodes = list(n.iter())
        h = next((d for d in nodes if d.tag in ('h1', 'h2')), None) or next((d for d in nodes if d.tag == 'h3'), None)
        out.append((collapse(node_text(h)) if h is not None else '', any('data-anim' in d.attrs for d in nodes)))
    return out


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
@media (max-width:820px){.row{grid-template-columns:1fr}header,section,footer{padding:16px}}
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
    a = ap.parse_args()
    if min(a.stage) <= 0:
        ap.error('--stage W H must be positive')

    before, after, prev = collect(a.before), collect(a.after), collect(a.previous)
    head, triage = read_triage(a.triage)
    deck = read_deck(a.deck)
    in_deck = {i for i, (_, anim) in enumerate(deck, 1) if anim}
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
    meta = [f'<b>{e(k)}:</b> {e(head[k])}' for k in HEAD_KEYS if k in head]
    meta.append(f'<b>{len(animated)} of {total}</b> slides animated; showing {len(shown)} '
                f'slide{"s" if len(shown) != 1 else ""}' + (' (animated only)' if a.only else '')
                + '. Animated slides show the resting frame, the state a PDF export shows.')
    parts = [f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
             f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title>'
             f'<style>{CSS}:root{{--cols:{cols};--ar:{a.stage[0]}/{a.stage[1]}}}</style></head><body>'
             f'<header><h1>{e(title)}</h1>' + ''.join(f'<p class="meta">{m}</p>' for m in meta) + '</header>']

    def fig(cls, src, cap, n):
        inner = (f'<img src="{e(img_src(src, out_dir, a.link_images))}" alt="{e(cap)}, slide {n}" loading="lazy">'
                 if src else 'no render')
        return f'<figure class="{cls}"><div class="box">{inner}</div><figcaption>{e(cap)}</figcaption></figure>'

    missing = []
    for n in shown:
        row = triage.get(n, {})
        name = row.get('title') or (deck[n - 1][0] if n <= len(deck) else '') or f'Slide {n}'
        anim = n in animated
        if n not in after:
            missing.append(n)
        figs = [fig('before', before[n], 'Original', n)]
        if a.previous:
            figs.append(fig('prev', prev.get(n), 'Previous attempt', n))
        figs.append(fig('after anim' if anim else 'after', after.get(n),
                        'Animated (resting frame)' if anim else 'Deck', n))
        dl = ''.join(f'<dt>{k.title()}</dt><dd>{e(row[k])}</dd>' for k in
                     ('decision', 'archetype', 'replaces', 'why') if row.get(k) and row[k] != '-')
        parts.append(f'<section><h2><span class="n">{n}</span>{e(name)}'
                     + ('<span class="tag">animated</span>' if anim else '') + '</h2>'
                     f'<div class="row">{"".join(figs)}</div>' + (f'<dl>{dl}</dl>' if dl else '') + '</section>')
    parts.append('<footer>generated by anim-slides review_page.py</footer></body></html>\n')
    os.makedirs(out_dir, exist_ok=True)
    with open(a.output, 'w', encoding='utf-8') as f:
        f.write(''.join(parts))
    if missing:
        lst = ', '.join(map(str, missing[:10])) + (f' ... ({len(missing)} in all)' if len(missing) > 10 else '')
        print(f'review_page: WARN no after render for slide(s) {lst}', file=sys.stderr)
    print(f'review_page: wrote {a.output}: {len(shown)} slide(s), {len(animated)} of {total} animated, '
          f'{cols} columns, images {"linked" if a.link_images else "embedded"} '
          f'({os.path.getsize(a.output) // 1024} KB)', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
