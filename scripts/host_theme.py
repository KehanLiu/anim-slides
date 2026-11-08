#!/usr/bin/env python3
"""Write the host theme block that retunes anim-slides fragments to a deck. Stdlib only.

Usage:
  host_theme.py DECK.html --mode match|lean [-o anim/host-theme.css] [--slide-selector SEL]
        [--json] [--apply DECK.html] [--backup]
  host_theme.py --apply DECK.html --from anim/host-theme.css [--backup]

Fragments read --anim-* tokens whose fallbacks are the lean dark palette
(references/fragment-contract.md section 3). A host retunes them by setting --anim-theme-*.
This script writes that block, so nobody hand-writes host glue.

  match  Fragments take the deck's palette and fonts. The deck's inline <style> blocks, local
         <link rel=stylesheet> files next to it (never the network), style="" attributes and
         SVG fill/stroke attributes are scanned for custom properties and the most used colours.
         Output: one ":root{--anim-theme-...}" rule. A table on stderr says where each value
         came from; check it. WARN lines flag fg/bg contrast < 4.5 and accent/bg < 3.
  lean   Fragments keep the lean palette, and each animated slide gets the lean ground.
         Output: the lean values as --anim-theme-* on ".anim-lean" plus a background/colour rule.
         Put class="anim-lean" on every slide that carries a fragment (only those).
         The font stays "inherit", so the deck's own font is kept.

  --slide-selector SEL  the deck's slide element (default: auto, ".slide" if the deck styles it,
         else "section"). match: the slide background is sampled from it first. lean: the ground
         rule also targets "SEL.anim-lean", which outranks the deck's own "SEL{background}".
  --json   print {"mode", "tokens", "sources", "warnings"} instead of CSS.
  -o FILE  write the CSS (or JSON) to FILE instead of stdout.
  --apply DECK.html  insert the block into that deck's <head> between
         <!-- anim-theme:start --> and <!-- anim-theme:end --> (before </head>); a second run
         replaces it in place. --backup writes DECK.html.bak first. Without --from the block is
         derived from DECK (the positional one); with -o as well, the same block goes to both
         (an existing -o file with different content, e.g. hand edits, is kept as FILE.bak).
  --from FILE  with --apply: insert exactly the block in FILE (the CSS that -o wrote, hand-
         corrected; or the part between the anim-theme markers if FILE has them). Nothing is
         derived, so --mode, -o, --json and --slide-selector are not used. This is the step after
         correcting a derived token by hand.

The block always starts with the line "/* anim-slides host theme (" so a newer one can be
pasted over an older one. Exit: 0 ok, 1 deck unreadable, 2 bad arguments.
"""
import argparse
import colorsys
import json
import os
import re
import shutil
import sys

TOKENS = ['bg', 'panel', 'line', 'fg', 'muted', 'accent', 'accent-2', 'ok', 'warn', 'danger',
          'font', 'mono']
LEAN = {'bg': '#0F1E27', 'panel': '#0D1820', 'line': '#2A3D49', 'fg': '#E6EDF0',
        'muted': '#93A7B2', 'accent': '#34D1BF', 'accent-2': '#FF8A3D', 'ok': '#8ED7AD',
        'warn': '#FFD15C', 'danger': '#FF6B6B', 'font': 'inherit',
        'mono': 'ui-monospace,SFMono-Regular,Menlo,monospace'}
LIGHT_STATUS = {'ok': '#1E8E3E', 'warn': '#B26A00', 'danger': '#C62828'}
NAMED = {'white': 'FFFFFF', 'black': '000000', 'red': 'FF0000', 'green': '008000',
         'blue': '0000FF', 'gray': '808080', 'grey': '808080', 'orange': 'FFA500',
         'yellow': 'FFFF00', 'navy': '000080', 'teal': '008080', 'silver': 'C0C0C0'}
MARK_START, MARK_END = '<!-- anim-theme:start -->', '<!-- anim-theme:end -->'
HEADER = '/* anim-slides host theme ('


# ---------- colour helpers ----------
def parse_color(s):
    """First colour in s as '#RRGGBB', or None. Alpha below 0.5 counts as no colour."""
    s = s.strip()
    m = re.search(r'#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b', s)
    m2 = re.search(r'rgba?\(\s*([\d.]+%?)[\s,]+([\d.]+%?)[\s,]+([\d.]+%?)(?:[\s,/]+([\d.]+%?))?\s*\)', s)
    m3 = re.search(r'\b(' + '|'.join(NAMED) + r')\b', s.lower())
    cands = [x for x in (m, m2, m3) if x]
    if not cands:
        return None
    first = min(cands, key=lambda x: x.start())
    if first is m:
        h = m.group(1)
        if len(h) in (3, 4):
            if len(h) == 4 and int(h[3], 16) < 8:
                return None
            h = ''.join(c * 2 for c in h[:3])
        elif len(h) == 8:
            if int(h[6:], 16) < 128:
                return None
            h = h[:6]
        return '#' + h.upper()
    if first is m2:
        def ch(v):
            return round(float(v[:-1]) * 2.55) if v.endswith('%') else round(float(v))
        a = m2.group(4)
        if a is not None and (float(a[:-1]) / 100 if a.endswith('%') else float(a)) < 0.5:
            return None
        return '#%02X%02X%02X' % tuple(max(0, min(255, ch(m2.group(i)))) for i in (1, 2, 3))
    return '#' + NAMED[m3.group(1)]


def rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))


def luminance(h):
    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def hls(h):
    return colorsys.rgb_to_hls(*rgb(h))  # hue 0..1, lightness, saturation


def chroma(h):
    c = rgb(h)
    return max(c) - min(c)


def mix(a, b, t):
    """a blended toward b by t (0..1)."""
    return '#%02X%02X%02X' % tuple(round((x + (y - x) * t) * 255) for x, y in zip(rgb(a), rgb(b)))


def hue_deg(h):
    return hls(h)[0] * 360


def hue_dist(a, b):
    d = abs(hue_deg(a) - hue_deg(b)) % 360
    return min(d, 360 - d)


def saturated(h):
    return chroma(h) >= 0.35


# ---------- CSS reading ----------
def read_sources(deck_path):
    html = open(deck_path, encoding='utf-8', errors='replace').read()
    html = re.sub(r'data:[^"\')\s]{64,}', 'data:', html)  # drop base64 payloads early
    # anim-slides' own blocks (fragments, an earlier theme) must not teach the deck's palette
    html = re.sub(r'<!--\s*(anim(?:-style)?:[\w-]+|anim-theme):start\s*-->.*?<!--\s*\1:end\s*-->', '',
                  html, flags=re.S)
    css = [s for s in re.findall(r'<style\b[^>]*>(.*?)</style\s*>', html, re.S | re.I)]
    linked = []
    base = os.path.dirname(os.path.abspath(deck_path))
    for tag in re.findall(r'<link\b[^>]*>', html, re.I):
        if not re.search(r'rel\s*=\s*["\']?stylesheet', tag, re.I):
            continue
        m = re.search(r'href\s*=\s*["\']([^"\']+)["\']', tag, re.I)
        if not m or re.match(r'[a-z][a-z0-9+.-]*:|//', m.group(1), re.I):
            continue  # network or other scheme: never fetched
        p = os.path.normpath(os.path.join(base, m.group(1).split('?')[0].split('#')[0]))
        if os.path.isfile(p):
            try:
                css.append(open(p, encoding='utf-8', errors='replace').read())
                linked.append(os.path.relpath(p, base))
            except OSError:
                pass
    css = re.sub(r'/\*.*?\*/', '', '\n'.join(css), flags=re.S)
    body = re.sub(r'<style\b[^>]*>.*?</style\s*>|<script\b[^>]*>.*?</script\s*>', '', html,
                  flags=re.S | re.I)
    return css, body, linked


def rules(css):
    """(selectors list, [(prop, value)]) for every innermost block; @media wrappers fall away."""
    out = []
    for m in re.finditer(r'([^{}]*)\{([^{}]*)\}', css):
        sel = m.group(1).strip()
        if sel.startswith('@'):
            continue
        sels = [s.strip() for s in sel.split(',') if s.strip()]
        if sels and all(re.search(r'\.anim(?:-[\w-]+)?\b', x) for x in sels):
            continue  # an inlined fragment's own rules (or a lean ground rule)
        decls = []
        for d in m.group(2).split(';'):
            if ':' in d:
                p, v = d.split(':', 1)
                p = p.strip().lower()
                if not p.startswith('--anim-'):
                    decls.append((p, v.replace('!important', '').strip()))
        out.append((sels, decls))
    return out


class Deck:
    def __init__(self, path):
        self.css, self.body, self.linked = read_sources(path)
        self.rules = rules(self.css)
        self.vars = {}
        for sels, decls in self.rules:
            if any(s in (':root', 'html', ':root, html') for s in sels):
                for p, v in decls:
                    if p.startswith('--'):
                        self.vars[p] = v
        for sels, decls in self.rules:  # vars defined elsewhere only fill gaps
            for p, v in decls:
                if p.startswith('--') and p not in self.vars:
                    self.vars[p] = v

    def resolve(self, v, depth=0):
        if depth > 8 or 'var(' not in v:
            return v

        def sub(m):
            name, fb = m.group(1), m.group(2)
            if name in self.vars:
                return self.resolve(self.vars[name], depth + 1)
            return self.resolve(fb or '', depth + 1)
        return self.resolve(re.sub(r'var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*(?:\([^()]*\)[^()]*)*))?\)',
                                   sub, v), depth + 1)

    def decl(self, selectors, props):
        """Last value of any of props in a rule whose selector list contains one of selectors."""
        found = None
        for sel in selectors:
            for sels, decls in self.rules:
                if sel in sels:
                    for p, v in decls:
                        if p in props:
                            found = (sel, p, v)
            if found:
                return found
        return None

    def var_color(self, pattern, ok=lambda c: True):
        """(name, colour) of the first var matching pattern (a regex alternation, tried in the
        order written) whose value is a colour that passes ok, else None."""
        alts = pattern.strip('^$()').split('|')
        for alt in alts:
            for name, v in self.vars.items():
                if re.fullmatch(alt, name[2:], re.I):
                    c = parse_color(self.resolve(v))
                    if c and ok(c):
                        return name, c
        return None

    def color_vars(self):
        """{colour: first var name} for vars holding a plain colour."""
        out = {}
        for name, v in self.vars.items():
            r = self.resolve(v).strip()
            if re.fullmatch(r'#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)', r) and parse_color(r):
                out.setdefault(parse_color(r), name)
        return out

    def color_counts(self):
        counts = {}  # colour -> {kind: n}
        kinds = {'background': 'background', 'background-color': 'background', 'color': 'color',
                 'fill': 'fill', 'stroke': 'stroke'}

        def add(c, k):
            if c:
                counts.setdefault(c, {}).setdefault(k, 0)
                counts[c][k] += 1
        decls = [d for _, ds in self.rules for d in ds]
        for attr in re.findall(r'\bstyle\s*=\s*"([^"]*)"', self.body, re.I):
            decls += [(p.strip().lower(), v.strip()) for p, v in
                      (d.split(':', 1) for d in attr.split(';') if ':' in d)]
        for p, v in decls:
            k = kinds.get(p) or ('border' if p.startswith('border') or p.startswith('outline') else None)
            if not k:
                continue
            v = self.resolve(v)
            for part in re.findall(r'#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)', v):
                add(parse_color(part), k)
        for p, v in re.findall(r'\b(fill|stroke)\s*=\s*"([^"]+)"', self.body):
            add(parse_color(self.resolve(v)), p)
        return counts


# ---------- derivation ----------
def derive_match(deck, slide_sel):
    tok, src, warns = {}, {}, []
    slide_sels = [slide_sel] if slide_sel else ['.slide', 'section', '.reveal .slides section',
                                                '.reveal']
    counts = deck.color_counts()

    def total(c, kind=None):
        return sum(counts.get(c, {}).values()) if kind is None else counts.get(c, {}).get(kind, 0)

    def from_rule(sels, props, label):
        d = deck.decl(sels, props)
        if d:
            c = parse_color(deck.resolve(d[2]))
            if c:
                return c, f'{d[0]} {{{d[1]}: {d[2][:40]}}}'
        return None

    # bg: slide background, then a slide-bg-like var, then body, then most used background
    r = (from_rule(slide_sels, ('background', 'background-color'), 'slide')
         or (lambda v: v and (v[1], v[0]))(deck.var_color(r'^(slide-?bg|slide-?background|bg-?primary|r-background-color|bg|background|surface-?0)$'))
         or from_rule(['body', 'html', ':root'], ('background', 'background-color'), 'body'))
    if not r:
        bgs = sorted(counts, key=lambda c: -total(c, 'background'))
        r = (bgs[0], 'most used colour in background') if bgs and total(bgs[0], 'background') else \
            ('#FFFFFF', 'default (nothing found)')
    tok['bg'], src['bg'] = r
    bg = tok['bg']
    dark = luminance(bg) < 0.2

    r = (from_rule(slide_sels, ('color',), 'slide') or from_rule(['body', 'html', ':root'], ('color',), 'body')
         or (lambda v: v and (v[1], v[0]))(deck.var_color(r'^(text-?primary|ink|fg|text|text-?color|foreground|r-main-color|body-?color|color-?text)$')))
    if not r or contrast(r[0], bg) < 3:
        fgs = sorted((c for c in counts if contrast(c, bg) >= 4.5), key=lambda c: -total(c, 'color'))
        r = (fgs[0], 'most used colour in color') if fgs and total(fgs[0], 'color') else \
            (('#E6EDF0', 'default for dark bg') if dark else ('#1A1A1A', 'default for light bg'))
    tok['fg'], src['fg'] = r
    fg = tok['fg']
    near = {bg, fg}

    def var_or(pattern, fallback, why, ok=lambda c: True):
        v = deck.var_color(pattern, ok=lambda c: c not in near and ok(c))
        return (v[1], v[0]) if v else (fallback, why)

    tok['panel'], src['panel'] = var_or(r'^(panel|bg-?secondary|bg-?card|surface|surface-?[12]|card|card-?bg|bg-?2|bg-?alt|subtle-?bg)$',
                                        mix(bg, fg, 0.05), 'bg mixed 5% toward fg')
    tok['line'], src['line'] = var_or(r'^(line|lines|border|border-?color|rule|divider|hairline|grid|stroke)$',
                                      mix(bg, fg, 0.22), 'bg mixed 22% toward fg')
    tok['muted'], src['muted'] = var_or(r'^(text-?secondary|text-?muted|muted|grey|gray|dim|subtle|secondary|text-?2|ink-?2|fg-?2|meta)$',
                                        mix(fg, bg, 0.4), 'fg mixed 40% toward bg',
                                        ok=lambda c: contrast(c, bg) >= 3)

    # accents: saturated colours, not near bg/fg, readable on bg, ranked by use x vividness
    sat = [c for c in counts if saturated(c) and contrast(c, bg) >= 1.6
           and min(contrast(c, x) for x in near) > 1.15]
    rank = sorted(sat, key=lambda c: -(total(c) * chroma(c) ** 2))
    named = deck.var_color(r'^(accent|accent-?primary|primary|brand|highlight|r-link-color|link)$', ok=saturated)
    def readable(c):  # on a light ground a dark saturated colour reads as text, so it must differ from fg
        return contrast(c, bg) >= 3 and (dark or contrast(c, fg) >= 1.8)
    if named:
        tok['accent'], src['accent'] = named[1], named[0]
    elif rank:
        top = rank[0]
        tok['accent'] = top
        src['accent'] = f'most used saturated colour ({total(top)} uses){var_name(deck, top)}'
        if not readable(top):
            # brand hue too close to fg or bg: take the most vivid shade of that hue the deck defines
            sib = sorted((c for c, n in deck.color_vars().items()
                          if saturated(c) and readable(c) and hue_dist(c, top) <= 20),
                         key=lambda c: -chroma(c))
            nxt = next((c for c in rank if readable(c)), None)
            if sib:
                tok['accent'] = sib[0]
                src['accent'] = (f'{deck.color_vars()[sib[0]]}: shade of the most used saturated colour '
                                 f'{top}{var_name(deck, top)}, which is too close to fg/bg')
            elif nxt:
                tok['accent'] = nxt
                src['accent'] = (f'most used saturated colour readable on bg and apart from fg '
                                 f'({total(nxt)} uses){var_name(deck, nxt)}')
    else:
        tok['accent'], src['accent'] = ('#34D1BF', 'default (no saturated colour)') if dark else \
            ('#0B6BCB', 'default (no saturated colour)')
    acc = tok['accent']
    rest = sorted((c for c in rank if c != acc and hue_dist(c, acc) >= 40),
                  key=lambda c: contrast(c, bg) < 3)  # readable ones first, rank kept within
    named2 = deck.var_color(r'^(accent-?2|accent-?secondary|secondary-?accent|accent-?alt|highlight-?2|accent-?glow)$', ok=saturated)
    if named2:
        tok['accent-2'], src['accent-2'] = named2[1], named2[0]
    elif rest:
        tok['accent-2'] = rest[0]
        src['accent-2'] = f'second saturated hue ({total(rest[0])} uses){var_name(deck, rest[0])}'
    else:
        tok['accent-2'], src['accent-2'] = '#FF8A3D' if dark else '#D9622B', 'default (no second hue)'

    status = {'ok': (r'^(ok|success|green|positive|good)$', (80, 170)),
              'warn': (r'^(warn|warning|amber|yellow|orange|caution)$', (30, 62)),
              'danger': (r'^(danger|error|red|negative|bad|alert)$', (-20, 15))}
    for key, (pat, (lo, hi)) in status.items():
        v = deck.var_color(pat, ok=saturated)
        if v:
            tok[key], src[key] = v[1], v[0]
            continue
        hits = [c for c in sat if lo <= (hue_deg(c) if hue_deg(c) <= 340 else hue_deg(c) - 360) <= hi]
        if hits:
            c = max(hits, key=total)
            tok[key], src[key] = c, f'most used {key} hue ({total(c)} uses){var_name(deck, c)}'
        else:
            tok[key] = LEAN[key] if dark else LIGHT_STATUS[key]
            src[key] = f'default for {"dark" if dark else "light"} bg'

    d = (deck.decl(['body', 'html', ':root'] + slide_sels, ('font-family',))
         or deck.decl(['body', 'html', ':root'] + slide_sels, ('font',)))
    if d:
        f = deck.resolve(d[2])
        if d[1] == 'font':  # shorthand: the family is what follows the size
            m = re.search(r'\d[\w.%]*(?:\s*/\s*[\w.%]+)?\s+(.+)$', f)
            f = m.group(1) if m else ''
        if f:
            tok['font'], src['font'] = clean_font(f), f'{d[0]} {{{d[1]}}}'
    if 'font' not in tok:  # no font rule: a declared font variable (body text first, then display)
        name = next((n for n in ('--font-body', '--font-sans', '--font-text', '--font',
                                 '--font-display', '--font-heading')
                     if deck.resolve(deck.vars.get(n, '')).strip()), None)
        if name:
            tok['font'], src['font'] = clean_font(deck.resolve(deck.vars[name])), name
    if 'font' not in tok:
        tok['font'], src['font'] = 'inherit', 'default (no font-family found)'
    mono_name = next((n for n in ('--font-mono', '--mono', '--font-code') if n in deck.vars), None) \
        or next((n for n in deck.vars if re.search(r'mono|code', n)), None)
    if mono_name:
        tok['mono'] = clean_font(deck.resolve(deck.vars[mono_name]))
        src['mono'] = mono_name
    else:
        fams = [deck.resolve(v) for _, ds in deck.rules for p, v in ds if p == 'font-family']
        hit = next((f for f in fams if re.search(r'mono|courier|consolas|menlo|code', f, re.I)), None)
        if hit:
            tok['mono'], src['mono'] = clean_font(hit), 'first monospace font-family'
        else:
            tok['mono'], src['mono'] = tok['font'], 'body font (no monospace family found)'

    cfb = contrast(fg, bg)
    if cfb < 4.5:
        warns.append(f'fg/bg contrast {cfb:.2f} < 4.5')
    cab = contrast(acc, bg)
    if cab < 3:
        warns.append(f'accent/bg contrast {cab:.2f} < 3')
    return tok, src, warns


def var_name(deck, c):
    names = [n for n, v in deck.vars.items() if parse_color(deck.resolve(v)) == c and 'var(' not in v]
    return f', = {names[0]}' if names else ''


def clean_font(f):
    return re.sub(r'\s*,\s*', ',', f.strip().rstrip(';').replace("'", '"'))


def auto_slide_selector(deck):
    for sel in ('.slide', 'section'):
        if any(sel in sels for sels, _ in deck.rules) or \
                (sel == '.slide' and re.search(r'class\s*=\s*"[^"]*\bslide\b', deck.body)) or \
                (sel == 'section' and '<section' in deck.body.lower()):
            return sel
    return None


# ---------- output ----------
def css_block(mode, tok, deck_name, slide_sel):
    body = ';'.join(f'--anim-theme-{k}:{tok[k]}' for k in TOKENS)
    if mode == 'match':
        return (f'{HEADER}match) — generated by host_theme.py from {deck_name} */\n'
                f':root{{{body}}}\n')
    ground = '.anim-lean' + (f',{slide_sel}.anim-lean' if slide_sel else '')
    return (f'{HEADER}lean) — generated by host_theme.py from {deck_name}; '
            f'put class="anim-lean" on each slide that carries a fragment */\n'
            f'.anim-lean{{{body}}}\n'
            f'{ground}{{background:{tok["bg"]};color:{tok["fg"]}}}\n')


def apply(path, block, backup):
    try:
        html = open(path, encoding='utf-8').read()
    except OSError as e:
        print(f'host_theme: cannot read {path}: {e}', file=sys.stderr)
        sys.exit(1)
    new = f'{MARK_START}<style>\n{block}</style>{MARK_END}'
    i, j = html.find(MARK_START), html.find(MARK_END)
    if i >= 0 and j > i:
        html = html[:i] + new + html[j + len(MARK_END):]
        what = 'replaced'
    else:
        m = list(re.finditer(r'</head\s*>', html, re.I))
        if not m:
            print(f'host_theme: no </head> in {path}', file=sys.stderr)
            sys.exit(1)
        k = m[0].start()
        html = html[:k] + new + '\n' + html[k:]
        what = 'inserted'
    if backup:
        shutil.copyfile(path, path + '.bak')
    open(path, 'w', encoding='utf-8').write(html)
    print(f'host_theme: {what} the theme block in {path}', file=sys.stderr)


def read_block(path):
    """The theme block in a corrected file: the text between the anim-theme markers (inside
    <style>) when present, else the whole file. Exits 1 when unreadable, 2 when not a block."""
    try:
        text = open(path, encoding='utf-8').read()
    except (OSError, UnicodeError) as e:
        print(f'host_theme: cannot read {path}: {e}', file=sys.stderr)
        sys.exit(1)
    i, j = text.find(MARK_START), text.find(MARK_END)
    if i >= 0 and j > i:
        text = text[i + len(MARK_START):j]
        text = re.sub(r'^\s*<style\b[^>]*>\n?|</style\s*>\s*$', '', text.strip() + '\n', flags=re.I)
    text = text.strip('\n') + '\n'
    if text.lstrip().startswith('{'):
        print(f'host_theme: {path} looks like --json output; --from needs the CSS block', file=sys.stderr)
        sys.exit(2)
    if '--anim-theme-' not in text or re.search(r'</?\s*[a-z!]', text, re.I):
        print(f'host_theme: {path} holds no anim theme block (want "--anim-theme-*" CSS, no HTML)',
              file=sys.stderr)
        sys.exit(2)
    if not text.startswith(HEADER):
        print(f'host_theme: WARN {path} does not start with "{HEADER}"; a later run cannot recognise '
              'it as an anim-slides theme', file=sys.stderr)
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split('\n', 2)[2])
    ap.add_argument('deck', nargs='?')
    ap.add_argument('--mode', choices=['match', 'lean'])
    ap.add_argument('-o', '--output')
    ap.add_argument('--slide-selector')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--apply', metavar='DECK')
    ap.add_argument('--backup', action='store_true')
    ap.add_argument('--from', dest='from_file', metavar='FILE')
    a = ap.parse_args()
    if a.backup and not a.apply:
        ap.error('--backup needs --apply')
    if a.from_file:
        if not a.apply:
            ap.error('--from needs --apply DECK')
        if a.output or a.json or a.slide_selector:
            ap.error('--from applies a finished block: -o, --json and --slide-selector do not apply')
        block = read_block(a.from_file)
        m = re.match(re.escape(HEADER) + r'(\w+)', block)
        print(f'host_theme: applying {a.from_file} as is ({m.group(1) if m else "unknown"} block, '
              'no derivation)' + (f'; --mode {a.mode} and {a.deck} are ignored' if a.mode or a.deck
                                  else ''), file=sys.stderr)
        apply(a.apply, block, a.backup)
        return 0
    if not a.deck or not a.mode:
        ap.error('DECK and --mode are required (or --apply DECK --from FILE)')
    if a.slide_selector is not None and not re.fullmatch(r'[\w.#\-\[\]="\' :>()]+', a.slide_selector):
        ap.error('--slide-selector: a plain CSS selector, no braces or semicolons')
    try:
        deck = Deck(a.deck)
    except (OSError, UnicodeError) as e:
        print(f'host_theme: cannot read {a.deck}: {e}', file=sys.stderr)
        return 1
    slide_sel = a.slide_selector or auto_slide_selector(deck)
    if a.mode == 'match':
        tok, src, warns = derive_match(deck, a.slide_selector)
        if deck.linked:
            print('host_theme: also read ' + ', '.join(deck.linked), file=sys.stderr)
        w = max(len(v) for v in tok.values())
        print(f'{"token":<10} {"value":<{w}}  source', file=sys.stderr)
        for k in TOKENS:
            print(f'{k:<10} {tok[k]:<{w}}  {src[k]}', file=sys.stderr)
        for x in warns:
            print(f'WARN {x}', file=sys.stderr)
    else:
        tok, src, warns = dict(LEAN), {k: 'lean fallback (fragment-contract.md section 3)' for k in LEAN}, []
        print('host_theme: put class="anim-lean" on each slide that carries a fragment'
              + (f' (ground rule also targets {slide_sel}.anim-lean)' if slide_sel else ''),
              file=sys.stderr)
    block = css_block(a.mode, tok, os.path.basename(a.deck), slide_sel)
    text = json.dumps({'mode': a.mode, 'tokens': tok, 'sources': src, 'warnings': warns},
                      indent=2) + '\n' if a.json else block
    if a.output:
        os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
        try:
            old = open(a.output, encoding='utf-8').read()
        except (OSError, UnicodeError):
            old = None
        if old is not None and old != text:
            shutil.copyfile(a.output, a.output + '.bak')
            print(f'host_theme: WARN {a.output} had different content (hand edits?); kept it as '
                  f'{a.output}.bak. To apply a corrected file use --apply DECK --from FILE',
                  file=sys.stderr)
        open(a.output, 'w', encoding='utf-8').write(text)
        print(f'host_theme: wrote {a.output}', file=sys.stderr)
    elif not a.apply or a.json:
        sys.stdout.write(text)
    if a.apply:
        print(f'host_theme: applying the block derived from {a.deck}'
              + (f' (the same block as {a.output})' if a.output and not a.json else ''),
              file=sys.stderr)
        apply(a.apply, block, a.backup)
    return 0


if __name__ == '__main__':
    sys.exit(main())
