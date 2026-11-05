#!/usr/bin/env python3
"""Inline an anim-slides fragment into a single-file HTML deck. Idempotent build step.

Usage:
  integrate_fragment.py DECK.html FRAGMENT.html --name NAME
        [--anchor STR] [--replace-until STR] [--wrap TAG] [--gate SELECTOR|none]
        [--dry-run] [--backup]

The fragment file is the source of truth; the deck holds a generated copy between markers:

  <head> ... <!-- anim-style:NAME:start --><style>...</style><!-- anim-style:NAME:end --> </head>
  <body> ... <!-- anim:NAME:start --> <div class="anim anim-NAME">...</div> <!-- anim:NAME:end -->

  - If the deck already has the markers, both blocks are replaced in place (--anchor not needed).
  - Otherwise the markup goes right after --anchor (a unique string in the slide); with
    --replace-until the text between the end of the anchor and the start of that string
    (e.g. a placeholder image) is replaced. The style block goes before </head>.
  - --wrap wraps the markup in an element: a tag name ("div") or a full opening tag
    ('<div class="figure">'); the closing tag is derived. Default: no wrap.
  - --gate rewrites the authored ".visible " gate prefix in the CSS (e.g. 'section.present'
    for reveal.js); "none" removes it so the animation always runs. Default: keep .visible.
  - Safety net: any class or id not prefixed NAME- (except anim, anim-NAME) is prefixed in
    markup and CSS, with a note per rename. Fix the fragment itself when you see one.
  - --backup writes DECK.html.bak first; --dry-run prints the summary without writing.
"""
import argparse
import re
import shutil
import sys


def die(msg):
    sys.exit(f'integrate_fragment: {msg}')


def load_fragment(path, name, gate):
    src = open(path, encoding='utf-8').read()
    styles = re.findall(r'<style[^>]*>(.*?)</style>', src, flags=re.S | re.I)
    if len(styles) != 1:
        die(f'fragment must contain exactly one <style>, found {len(styles)}')
    css = styles[0].strip('\n')
    body = re.sub(r'<style[^>]*>.*?</style>', '', src, flags=re.S | re.I).strip()
    if not re.search(r'class="[^"]*\banim-' + re.escape(name) + r'\b', body):
        die(f'root div must carry class "anim anim-{name}" (wrong --name?)')
    for bad in ('<image', '<link', '@import', '@font-face'):
        if bad in src:
            die(f'fragment contains {bad!r}; run check_fragment.py')
    if re.search(r'<script(?![^>]*type="module")', body):
        die('fragment contains a non-module <script>; run check_fragment.py')

    pref = name + '-'
    keep = {'anim', f'anim-{name}', 'visible'}
    markup = re.sub(r'<script\b.*?</script>', '', body, flags=re.S)
    classes, ids = set(), set()
    for attr in re.findall(r'\bclass="([^"]*)"', markup):
        classes.update(t for t in attr.split() if t not in keep and not t.startswith(pref))
    for i in re.findall(r'\bid="([^"]+)"', markup):
        if not i.startswith(pref):
            ids.add(i)
    notes = []
    if classes:
        body = re.sub(r'\bclass="([^"]*)"', lambda m: 'class="' + ' '.join(
            pref + t if t in classes else t for t in m.group(1).split()) + '"', body)
        for c in sorted(classes):
            css = re.sub(r'\.' + re.escape(c) + r'(?![\w-])', '.' + pref + c, css)
            notes.append(f'note: class "{c}" renamed to "{pref}{c}"')
    for i in sorted(ids):
        body = re.sub(r'\bid="' + re.escape(i) + '"', f'id="{pref}{i}"', body)
        body = re.sub(r'(href="|url\()#' + re.escape(i) + r'(?![\w-])', r'\1#' + pref + i, body)
        css = re.sub(r'(#|url\(#)' + re.escape(i) + r'(?![\w-])', r'\1' + pref + i, css)
        notes.append(f'note: id "{i}" renamed to "{pref}{i}"')
    if (classes or ids) and '<script' in body:
        notes.append('note: the fragment script may still reference the old names; check it')

    # gate rewrite: ".visible " at the start of a selector, just before .anim-NAME
    gate_re = re.compile(r'(^|[,{}]\s*)\.visible\s+(?=\.anim-' + re.escape(name) + r'(?![\w-]))', re.M)
    n_gate = len(gate_re.findall(css))
    if gate is not None and gate.strip() != '.visible':
        repl = '' if gate.strip().lower() == 'none' else gate.strip() + ' '
        css = gate_re.sub(lambda m: m.group(1) + repl, css)
    return css, body, notes, n_gate, len(classes) + len(ids)


def wrap_markup(body, wrap):
    if not wrap:
        return body
    w = wrap.strip()
    if not w.startswith('<'):
        w = f'<{w}>'
    tag = re.match(r'<\s*([A-Za-z][\w-]*)', w)
    if not tag:
        die(f'--wrap {wrap!r} is not a tag')
    return f'{w}\n{body}\n</{tag.group(1)}>'


def replace_block(s, start, end, new):
    """Replace start..end (inclusive) if present. Returns (s, replaced?)."""
    i = s.find(start)
    if i < 0:
        return s, False
    j = s.find(end, i)
    if j < 0:
        die(f'found {start} without {end}')
    if s.find(start, i + 1) >= 0:
        die(f'{start} appears twice in the deck')
    return s[:i] + new + s[j + len(end):], True


def main():
    ap = argparse.ArgumentParser(description='Inline an anim-slides fragment into a deck (idempotent).')
    ap.add_argument('deck')
    ap.add_argument('fragment')
    ap.add_argument('--name', required=True)
    ap.add_argument('--anchor', help='unique string; needed only on first insertion')
    ap.add_argument('--replace-until', help='replace from the end of --anchor up to this string')
    ap.add_argument('--wrap', default='', help='tag name or opening tag wrapped around the markup')
    ap.add_argument('--gate', default=None, help="gate selector for the host, or 'none' (default: keep .visible)")
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--backup', action='store_true')
    a = ap.parse_args()
    n = a.name

    css, body, notes, n_gate, renamed = load_fragment(a.fragment, n, a.gate)
    for m in notes:
        print(m, file=sys.stderr)
    s = open(a.deck, encoding='utf-8').read()
    orig = s

    m_start, m_end = f'<!-- anim:{n}:start -->', f'<!-- anim:{n}:end -->'
    s_start, s_end = f'<!-- anim-style:{n}:start -->', f'<!-- anim-style:{n}:end -->'
    markup_block = f'{m_start}\n{wrap_markup(body, a.wrap)}\n{m_end}'
    style_block = f'{s_start}\n<style>\n{css}\n</style>\n{s_end}'

    # refuse a legacy (marker-less) copy, it would end up twice in the deck
    unmarked = re.sub(re.escape(m_start) + '.*?' + re.escape(m_end), '', s, flags=re.S)
    unmarked = re.sub(re.escape(s_start) + '.*?' + re.escape(s_end), '', unmarked, flags=re.S)
    if re.search(r'anim-' + re.escape(n) + r'(?![\w-])', unmarked):
        die(f'deck contains anim-{n} outside the anim:{n} markers (an older copy?); remove it once by hand')

    s, replaced = replace_block(s, m_start, m_end, markup_block)
    if not replaced:
        if not a.anchor:
            die(f'deck has no {m_start} block yet; pass --anchor')
        c = s.count(a.anchor)
        if c != 1:
            die(f'--anchor must occur exactly once, found {c}')
        i = s.index(a.anchor) + len(a.anchor)
        if a.replace_until:
            j = s.find(a.replace_until, i)
            if j < 0:
                die('--replace-until not found after the anchor')
            s = s[:i] + '\n' + markup_block + '\n' + s[j:]
        else:
            s = s[:i] + '\n' + markup_block + s[i:]

    s, style_replaced = replace_block(s, s_start, s_end, style_block)
    if not style_replaced:
        k = s.lower().find('</head>')
        if k < 0:
            k = s.lower().find('<body')
        if k < 0:
            k = 0
        s = s[:k] + style_block + '\n' + s[k:]

    gate_used = '.visible' if a.gate is None else a.gate
    if n_gate == 0:
        gate_used += ' (no gated rules found)'
    action = 'replaced' if replaced else 'inserted'
    unchanged = ' (no change)' if s == orig else ''
    print(f'{action} anim-{n} in {a.deck}{unchanged}: style {len(css.encode())} bytes, '
          f'gate {gate_used} ({n_gate} rules), {renamed} name(s) renamed'
          + (' [dry run, nothing written]' if a.dry_run else ''))
    if a.dry_run or s == orig:
        return
    if a.backup:
        shutil.copy(a.deck, a.deck + '.bak')
    open(a.deck, 'w', encoding='utf-8').write(s)


if __name__ == '__main__':
    main()
