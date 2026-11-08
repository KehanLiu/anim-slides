#!/usr/bin/env python3
"""Inline an anim-slides fragment into a single-file HTML deck. Idempotent build step.

Usage:
  integrate_fragment.py DECK.html FRAGMENT.html --name NAME
        [--anchor STR] [--replace-until STR] [--wrap TAG] [--gate SELECTOR|none]
        [--control once|step] [--no-print-guard] [--dry-run] [--backup]

The fragment file is the source of truth; the deck holds a generated copy between markers:

  <head> ... <!-- anim-style:NAME:start --><style>...</style><!-- anim-style:NAME:end --> </head>
  <body> ... <!-- anim:NAME:start --> <div class="anim anim-NAME">...</div> <!-- anim:NAME:end -->

  - If the deck already has the markers, both blocks are replaced in place (--anchor not needed).
  - Otherwise the markup goes right after --anchor (a unique string in the slide). With
    --replace-until, the anchor and the until-string themselves are kept; everything between
    them (e.g. a placeholder image) is replaced. The style block goes before </head>.
  - --wrap wraps the markup in an element: a tag name ("div") or a full opening tag
    ('<div class="figure">'); the closing tag is derived. Default: no wrap.
  - --gate rewrites the authored ".visible " gate prefix in the CSS (e.g. 'section.present'
    for reveal.js); "none" removes it so the animation always runs. Default: keep .visible.
  - --control sets data-anim-control on the wrapper in the deck (default: keep the fragment's
    own attribute). The fragment file is the same under once and step: CSS keyframes, one pass.
      once  the pass plays when the slide becomes current; a step-host snippet already in the
            deck is left alone (it ignores once wrappers).
      step  the presenter steps through the pass: the wrapper must carry data-anim-phases (stop
            marks in seconds; refused otherwise) and the deck <head> gets the step host
            (scripts/snippets/step-host.html, plain CSS + script, no library) once, between
            <!-- anim-slides:step-host:start --> and :end markers; a later run replaces that
            block with the current snippet. A --gate other than .visible is written into the
            block as animSlides.gate = '...', so host and CSS use the same gate (pass the same
            --gate on every run). --gate none is refused: the host needs the gate to know the current slide.
  - Print guard: the style block ends with rules that switch the fragment's animations off in
    print and in known print-layout modes (reveal.js ?print-pdf marks EVERY slide .present), so a
    PDF export shows the resting frame, not a mid-cycle frame. --no-print-guard leaves it out.
  - HTML comments starting with "scaffold" or "refine" (scaffold_from_spec.py notes) are dropped.
  - Safety net: any class or id not prefixed NAME- (except anim, anim-NAME) is prefixed in
    markup and CSS, with a note per rename. Fix the fragment itself when you see one.
  - --backup writes DECK.html.bak first; --dry-run prints the summary without writing.
"""
import argparse
import os
import re
import shutil
import sys

HOST_START, HOST_END = '<!-- anim-slides:step-host:start -->', '<!-- anim-slides:step-host:end -->'
HOST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'snippets', 'step-host.html')


def die(msg):
    sys.exit(f'integrate_fragment: {msg}')


def load_fragment(path, name, gate):
    src = open(path, encoding='utf-8').read()
    # authoring notes (scaffold_from_spec.py header, "refine by hand" notes) stay out of the deck
    src = re.sub(r'[ \t]*<!--\s*(?:scaffold|refine)\b.*?-->[ \t]*\n?', '', src, flags=re.S | re.I)
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
    if re.search(r'<script\b', body, re.I):
        die('fragment contains a <script>; fragments are CSS only (step mode is driven by the deck\'s '
            'step host), run check_fragment.py')

    pref = name + '-'
    keep = {'anim', f'anim-{name}', 'visible'}
    markup = body
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

    # gate rewrite: ".visible " at the start of a selector, just before .anim-NAME
    gate_re = re.compile(r'(^|[,{}]\s*)\.visible\s+(?=\.anim-' + re.escape(name) + r'(?![\w-]))', re.M)
    n_gate = len(gate_re.findall(css))
    if gate is not None and gate.strip() != '.visible':
        repl = '' if gate.strip().lower() == 'none' else gate.strip() + ' '
        css = gate_re.sub(lambda m: m.group(1) + repl, css)
    return css, body, notes, n_gate, len(classes) + len(ids)


PRINT_MODES = ('html.print-pdf', 'html.reveal-print')   # reveal.js print layout classes


def print_guard(name):
    """CSS that shows the resting frame in print / PDF export, whatever the gate says."""
    root = f'.anim-{name}'
    sels = ', '.join(f'{m} {root}, {m} {root} *' for m in PRINT_MODES)
    return (f'/* anim-slides print guard: PDF export shows the resting frame */\n'
            f'@media print {{ {root}, {root} * {{ animation: none !important; transition: none !important; }} }}\n'
            f'{sels} {{ animation: none !important; transition: none !important; }}')


def set_control(body, name, control):
    """Set data-anim-control on the wrapper's opening tag. Returns (body, control, phases)."""
    m = re.search(r'<div\b[^>]*\bclass="[^"]*\banim-' + re.escape(name) + r'(?![\w-])[^>]*>', body)
    if not m:
        die(f'no <div class="anim anim-{name}"> opening tag found')
    tag = m.group(0)
    cur = re.search(r'\sdata-anim-control="([^"]*)"', tag)
    phases = re.search(r'\sdata-anim-phases="([^"]*)"', tag)
    if control and (not cur or cur.group(1) != control):
        tag = (tag.replace(cur.group(0), f' data-anim-control="{control}"') if cur
               else tag[:-1].rstrip('/').rstrip() + f' data-anim-control="{control}">')
        body = body[:m.start()] + tag + body[m.end():]
    return body, control or (cur.group(1) if cur else 'once'), phases.group(1) if phases else None


def step_host(s, gate):
    """Insert or refresh the step-host block in <head>. Returns (s, what happened)."""
    snippet = open(HOST_FILE, encoding='utf-8').read().strip()
    if HOST_START not in snippet or not snippet.endswith(HOST_END):
        die(f'{HOST_FILE} lacks the step-host markers')
    old = None
    i = s.find(HOST_START)
    if i >= 0:
        j = s.find(HOST_END, i)
        if j < 0:
            die(f'found {HOST_START} without {HOST_END}')
        old = s[i:j + len(HOST_END)]
    elif 'anim-slides step host' in s or 'animSlides.register' in s:
        die('deck has an older (GSAP) step host without the anim-slides:step-host markers; remove it '
            '(and the GSAP script, if nothing else uses it) once by hand, then re-run')
    g = (gate or '.visible').strip()   # the host gate follows the CSS gate (--gate)
    line = '' if g == '.visible' else "<script>animSlides.gate = '" + g.replace("'", "\\'") + "';</script>"
    block = snippet[:-len(HOST_END)] + (line + '\n' if line else '') + HOST_END
    if old is not None:
        return s.replace(old, block), ('step host up to date' if old == block else 'step host updated')
    k = s.lower().find('</head>')
    if k < 0:
        die('deck has no </head>; the step host goes in <head>')
    return s[:k] + block + '\n' + s[k:], 'step host inserted'


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
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('deck')
    ap.add_argument('fragment')
    ap.add_argument('--name', required=True)
    ap.add_argument('--anchor', help='unique string; needed only on first insertion')
    ap.add_argument('--replace-until', help='replace the text between --anchor and this string; '
                    'the anchor and the until-string themselves are kept')
    ap.add_argument('--wrap', default='', help='tag name or opening tag wrapped around the markup')
    ap.add_argument('--gate', default=None, help="gate selector for the host, or 'none' (default: keep .visible)")
    ap.add_argument('--control', choices=['once', 'step'], default=None,
                    help="set data-anim-control on the wrapper (default: keep the fragment's own)")
    ap.add_argument('--no-print-guard', action='store_true',
                    help='do not add the rules that freeze the fragment on its resting frame in print/PDF')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--backup', action='store_true')
    a = ap.parse_args()
    n = a.name

    css, body, notes, n_gate, renamed = load_fragment(a.fragment, n, a.gate)
    body, control, phases = set_control(body, n, a.control)
    if control == 'step':
        if not phases:
            die('control step needs data-anim-phases="<s>,<s>,..." on the fragment wrapper (the stop marks '
                'in seconds); add it to the fragment file and run check_fragment.py --control step')
        if a.gate is not None and a.gate.strip().lower() == 'none':
            die('--control step needs a gate: the step host plays a fragment when its slide becomes current')
    if not a.no_print_guard:
        css = css.rstrip() + '\n' + print_guard(n)
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

    host_note = ''
    if control == 'step':
        s, host_note = step_host(s, a.gate)
        host_note = f', control step (marks {phases} s), {host_note}'
    elif HOST_START in s:
        host_note = f', control {control} (step host present, ignores this fragment)'
    else:
        host_note = f', control {control}'
    gate_used = '.visible' if a.gate is None else a.gate
    if n_gate == 0:
        gate_used += ' (no gated rules found)'
    action = 'replaced' if replaced else 'inserted'
    unchanged = ' (no change)' if s == orig else ''
    print(f'{action} anim-{n} in {a.deck}{unchanged}: style {len(css.encode())} bytes, '
          f'gate {gate_used} ({n_gate} rules), {renamed} name(s) renamed{host_note}'
          + (' [dry run, nothing written]' if a.dry_run else ''))
    if a.dry_run or s == orig:
        return
    if a.backup:
        shutil.copy(a.deck, a.deck + '.bak')
    open(a.deck, 'w', encoding='utf-8').write(s)


if __name__ == '__main__':
    main()
