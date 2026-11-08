#!/usr/bin/env python3
"""Hand-over checks for a whole page or deck that carries anim-slides fragments.

Usage:
  check_page.py PAGE.html [--gate SELECTOR|none] [--allow-external]

  --gate            gate selector every embedded fragment must use (e.g. 'section.present');
                    default: detect it from the page (reveal.js -> 'section.present'; a script
                    that adds class "visible", as md_to_deck.py decks and the observer snippet
                    do -> '.visible') and say which; when neither is found, require some gate
                    per fragment; 'none' accepts ungated (always-on) animations
  --allow-external  report external resources as WARN instead of FAIL

Checks:
  external   script src, link href, img/source/video/audio/iframe/embed src, srcset, poster,
             object data, <use>/<image> href, @import and url() in <style> and style="" that
             point to http(s):// or protocol-relative (//host) URLs. FAIL unless
             --allow-external, except stylesheet/preconnect links and url()s to a web-font host
             (Google Fonts, Fontshare, Typekit, Bunny): one WARN, the deck's own load. file:// URLs always FAIL; missing local files FAIL; present
             local files WARN (the page is not one file yet: run bundle_deck.py).
  markers    every <!-- anim:NAME:start --> has one end marker after it and a matching
             anim-style:NAME pair; no name is used twice (markers or data-anim).
  gate       inside each anim-style block, every rule that sets an animation (outside
             @keyframes, reduced-motion and print blocks) is prefixed by the gate.
  step       every data-anim-control="step" wrapper carries data-anim-phases, and <head> holds
             the step host (<!-- anim-slides:step-host:start --> ... :end, from
             integrate_fragment.py --control step); FAIL otherwise. A step host without step
             wrappers is OK (it ignores once fragments). An older script-driven host
             (animSlides.register) FAILs: fragments are CSS only.
  print      each fragment has a print guard: an @media print rule (or an html.print-pdf /
             html.reveal-print rule) that sets animation: none on .anim-NAME, so a PDF export
             shows the resting frame. OK or WARN per fragment.
  leftovers  preview / render artefacts: --virtual-time-budget, the render-phases pause style
             (animation-play-state:paused !important), <base href="file://...">, preview- names,
             scaffold "refine by hand" notes. The step host's own paused rule is not a leftover.

Prints OK / WARN / FAIL with line numbers. Exit code 1 on any FAIL. Standard library only.
"""
import argparse
import os
import re
import sys

EXT = re.compile(r'^(?:https?:)?//', re.I)
# web-font hosts: a deck skill's own font link is the deck's load (WARN, not FAIL)
FONT_HOSTS = ('fonts.googleapis.com', 'fonts.gstatic.com', 'api.fontshare.com', 'cdn.fontshare.com',
              'use.typekit.net', 'fonts.bunny.net')


def font_host(u):
    m = re.match(r'^(?:https?:)?//([^/:?#]+)', u, re.I)
    return bool(m) and m.group(1).lower() in FONT_HOSTS


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, check, msg, line=None):
        self.items.append((level, check, msg + (f' (line {line})' if line else '')))

    def ok(self, check, msg):
        self.add('OK', check, msg)

    def warn(self, check, msg, line=None):
        self.add('WARN', check, msg, line)

    def fail(self, check, msg, line=None):
        self.add('FAIL', check, msg, line)

    def print(self):
        seen = set()
        for lvl, chk, msg in self.items:
            if (lvl, chk, msg) in seen:
                continue
            seen.add((lvl, chk, msg))
            print(f'{lvl:<4} {chk}: {msg}')
        nf = sum(1 for i in self.items if i[0] == 'FAIL')
        nw = sum(1 for i in self.items if i[0] == 'WARN')
        print(f'{"PASS" if nf == 0 else "FAILED"}: {nf} fail, {nw} warn')
        return nf


def blank(m):
    """Replace a match by spaces, keeping newlines, so positions and line numbers survive."""
    return re.sub(r'[^\n]', ' ', m.group(0))


# ----------------------------------------------------------------------------- css
def strip_css_comments(css):
    return re.sub(r'/\*.*?\*/', blank, css, flags=re.S)


def parse_css(css, base=0):
    """[(prelude, start, body_or_children, is_block)] for a comment-free stylesheet."""
    out, i, n = [], 0, len(css)
    while i < n:
        j = css.find('{', i)
        if j < 0:
            break
        semi = css.find(';', i, j)
        if semi >= 0 and css[i:semi].strip().startswith('@'):   # @import x; @charset ...
            i = semi + 1
            continue
        prelude = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            depth += {'{': 1, '}': -1}.get(css[k], 0)
            k += 1
        inner = css[j + 1:k - 1]
        if prelude.startswith('@') and not prelude.lower().startswith(('@font-face', '@page')):
            out.append((prelude, base + i, parse_css(inner, base + j + 1), True))
        else:
            out.append((prelude, base + i, inner, False))
        i = k
    return out


def animated_rules(nodes, skip=False):
    """Yield (selector, pos) of rules that start an animation, outside keyframes/print/reduced."""
    for prelude, pos, body, is_block in nodes:
        low = prelude.lower()
        if is_block:
            if low.startswith('@keyframes') or low.startswith('@-webkit-keyframes'):
                continue
            sub = skip or 'print' in low or 'reduce' in low
            yield from animated_rules(body, sub)
            continue
        if skip:
            continue
        m = re.search(r'(?:^|;)\s*animation(?:-name)?\s*:\s*([^;]*)', body, re.I)
        if not m or re.match(r'\s*none\b', m.group(1), re.I):
            continue
        for sel in prelude.split(','):
            yield ' '.join(sel.split()), pos


def style_chunk(raw, nm):
    """(offset, css text) of fragment nm's style: its anim-style block, else a <style> naming it."""
    blk = re.search(r'<!--\s*anim-style:' + re.escape(nm) + r':start\s*-->(.*?)<!--\s*anim-style:'
                    + re.escape(nm) + r':end\s*-->', raw, re.S)
    if blk:
        return blk.start(1), blk.group(1)
    for m in re.finditer(r'<style\b[^>]*>(.*?)</style\s*>', raw, re.S | re.I):
        if f'.anim-{nm}' in m.group(1):
            return m.start(1), m.group(1)
    return 0, ''


def css_nodes(off, chunk):
    """Parsed CSS of a style chunk (which may hold several <style> elements)."""
    parts = [(off + m.start(1), m.group(1)) for m in re.finditer(r'<style\b[^>]*>(.*?)</style\s*>', chunk, re.S | re.I)] \
        if '<style' in chunk.lower() else [(off, chunk)]
    nodes = []
    for o, c in parts:
        nodes += parse_css(strip_css_comments(c), o)
    return nodes


def print_guard(raw, nm):
    """(position, found) of a rule that stops nm's animations in print / print-layout modes."""
    off, chunk = style_chunk(raw, nm)
    root = f'.anim-{nm}'
    stop = re.compile(r'(?:^|;)\s*animation(?:-name)?\s*:\s*none\b', re.I)

    def walk(nodes, in_print):
        for prelude, pos, body, is_block in nodes:
            if is_block:
                low = prelude.lower()
                if low.startswith(('@keyframes', '@-webkit-keyframes')):
                    continue
                if walk(body, in_print or re.search(r'@media[^{]*\bprint\b', low) is not None):
                    return True
            elif root in prelude and stop.search(body) and (
                    in_print or re.search(r'html\.(?:print-pdf|reveal-print)\b', prelude)):
                return True
        return False
    return off, walk(css_nodes(off, chunk), False)


def detect_gate(raw, names):
    """(gate, reason) for the host page, or (None, '')."""
    reveal = re.search(r'Reveal\.initialize|class\s*=\s*["\'][^"\']*\breveal\b|reveal(?:\.min)?\.js', raw)
    visible = re.search(r'classList\.(?:add|toggle)\(\s*[\'"]visible[\'"]', raw)
    cands = []
    if reveal:
        cands.append(('section.present', 'reveal.js page: the current slide is section.present'))
    if visible:
        cands.append(('.visible', 'a page script adds class "visible" to the current slide or section'))
    if len(cands) < 2:
        return cands[0] if cands else (None, '')
    used = ' '.join(css for _, css in (style_chunk(raw, nm) for nm in names))
    for g, why in cands:   # both found: take the one the fragments use
        if re.search(re.escape(g) + r'\s+\.anim-', used):
            return g, why + '; the fragments use it'
    return cands[0]


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('page')
    ap.add_argument('--gate', default=None)
    ap.add_argument('--allow-external', action='store_true')
    a = ap.parse_args()
    raw = open(a.page, encoding='utf-8', errors='replace').read()
    base_dir = os.path.dirname(os.path.abspath(a.page))
    R = Report()

    def line_of(pos):
        return raw.count('\n', 0, pos) + 1

    # comments and inline script bodies are not resources; blank them for the resource scan
    nocomment = re.sub(r'<!--.*?-->', blank, raw, flags=re.S)
    scan = re.sub(r'(<script\b[^>]*>)(.*?)(</script\s*>)',
                  lambda m: m.group(1) + blank(re.match(r'.*', m.group(2), re.S)) + m.group(3),
                  nocomment, flags=re.S | re.I)

    # ---- external resources
    refs = []   # (url, pos, what)
    attr_re = re.compile(r'''\s((?:xlink:)?href|src|srcset|poster|data)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))''', re.I)
    for t in re.finditer(r'<(script|link|img|source|video|audio|iframe|embed|object|use|image|track|input)\b([^>]*)>',
                         scan, re.I):
        tag = t.group(1).lower()
        attrs = t.group(2)
        if tag == 'link':
            rel = re.search(r'''\brel\s*=\s*["']?([^"'>]+)''', attrs, re.I)
            rel = rel.group(1).lower() if rel else ''
            if not re.search(r'stylesheet|icon|preload|modulepreload|manifest', rel):
                hm = re.search(r'''\shref\s*=\s*["']?([^"'\s>]+)''', attrs, re.I)
                if re.search(r'preconnect|dns-prefetch', rel) and hm and font_host(hm.group(1)):
                    refs.append((hm.group(1), t.start() + hm.start(), '<link preconnect>'))
                continue
        for m in attr_re.finditer(attrs):
            an, val = m.group(1).lower(), m.group(2) or m.group(3) or m.group(4) or ''
            if tag == 'object' and an != 'data':
                continue
            if an == 'data' and tag != 'object':
                continue
            urls = [u.strip().split()[0] for u in val.split(',') if u.strip()] if an == 'srcset' else [val.strip()]
            for u in urls:
                refs.append((u, t.start() + m.start(), f'<{tag} {an}>'))
    css_spans = [(m.start(1), m.group(1)) for m in re.finditer(r'<style\b[^>]*>(.*?)</style\s*>', scan, re.S | re.I)]
    css_spans += [(m.start(2), m.group(2)) for m in
                  re.finditer(r'''\sstyle\s*=\s*(["'])(.*?)\1''', scan, re.S | re.I)]
    for off, css in css_spans:
        css = strip_css_comments(css)
        imports = []
        for m in re.finditer(r'''@import\s+(?:url\(\s*)?["']?([^"')\s;]+)[^;]*;?''', css, re.I):
            refs.append((m.group(1), off + m.start(), '@import'))
            imports.append((m.start(), m.end()))
        for m in re.finditer(r'''url\(\s*["']?([^"')]+?)["']?\s*\)''', css, re.I):
            if not any(s0 <= m.start() < e0 for s0, e0 in imports):
                refs.append((m.group(1), off + m.start(), 'url()'))
    n_ext = n_local = 0
    fonts = []   # (url, line) to web-font hosts
    for u, pos, what in refs:
        if not u or u.startswith(('data:', '#', 'blob:', 'about:', 'javascript:')) or u.startswith('var('):
            continue
        ln = line_of(pos)
        if EXT.match(u) and font_host(u):
            n_ext += 1
            fonts.append((u, ln))
        elif EXT.match(u):
            n_ext += 1
            (R.warn if a.allow_external else R.fail)('external', f'{what} {u}', ln)
        elif u.lower().startswith('file:'):
            R.fail('external', f'{what} {u}: absolute file:// path breaks on any other machine', ln)
        else:
            path = os.path.join(base_dir, re.split(r'[?#]', u)[0])
            n_local += 1
            if not os.path.exists(path):
                R.fail('external', f'{what} {u}: local file not found', ln)
            else:
                R.warn('external', f'{what} {u}: local file, the page is not one file yet (bundle_deck.py)', ln)
    if fonts:
        hosts = sorted({re.match(r'^(?:https?:)?//([^/:?#]+)', u, re.I).group(1).lower() for u, _ in fonts})
        R.warn('external', 'web font link (the deck\'s own load; bundle with bundle_deck.py --fetch for hand-over): '
               f'{", ".join(hosts)}, {len(fonts)} reference(s)', fonts[0][1])
    if n_ext == 0 and n_local == 0:
        R.ok('external', 'no external or local resources: the page is self-contained')
    elif n_ext == 0:
        R.ok('external', 'no remote resources')

    # ---- markers
    starts = [(m.group(1), m.start()) for m in re.finditer(r'<!--\s*anim:([\w-]+):start\s*-->', raw)]
    ends = [(m.group(1), m.start()) for m in re.finditer(r'<!--\s*anim:([\w-]+):end\s*-->', raw)]
    sstarts = [(m.group(1), m.start()) for m in re.finditer(r'<!--\s*anim-style:([\w-]+):start\s*-->', raw)]
    sends = [(m.group(1), m.start()) for m in re.finditer(r'<!--\s*anim-style:([\w-]+):end\s*-->', raw)]
    names = []
    for kind, ss, ee in (('anim', starts, ends), ('anim-style', sstarts, sends)):
        for nm in sorted({n for n, _ in ss} | {n for n, _ in ee}):
            s_pos = [p for n, p in ss if n == nm]
            e_pos = [p for n, p in ee if n == nm]
            if len(s_pos) > 1:
                R.fail('markers', f'{kind}:{nm}:start appears {len(s_pos)} times (name used twice)', line_of(s_pos[1]))
            if len(e_pos) > 1:
                R.fail('markers', f'{kind}:{nm}:end appears {len(e_pos)} times', line_of(e_pos[1]))
            if s_pos and not e_pos:
                R.fail('markers', f'{kind}:{nm}:start has no end marker', line_of(s_pos[0]))
            elif e_pos and not s_pos:
                R.fail('markers', f'{kind}:{nm}:end has no start marker', line_of(e_pos[0]))
            elif s_pos and e_pos and e_pos[0] < s_pos[0]:
                R.fail('markers', f'{kind}:{nm}:end comes before its start', line_of(e_pos[0]))
    mk_names = [n for n, _ in starts]
    st_names = [n for n, _ in sstarts]
    for nm in sorted(set(mk_names) - set(st_names)):
        R.fail('markers', f'anim:{nm} has no anim-style:{nm} block', line_of(dict(starts)[nm]))
    for nm in sorted(set(st_names) - set(mk_names)):
        R.fail('markers', f'anim-style:{nm} has no anim:{nm} markup block', line_of(dict(sstarts)[nm]))
    da = {}
    for m in re.finditer(r'''\sdata-anim\s*=\s*["']([\w-]+)["']''', nocomment):
        da.setdefault(m.group(1), []).append(m.start())
    for nm, ps in sorted(da.items()):
        if len(ps) > 1:
            R.fail('markers', f'data-anim="{nm}" appears {len(ps)} times: two fragments share a name', line_of(ps[1]))
    for nm in sorted(set(da) - set(mk_names)):
        R.warn('markers', f'fragment "{nm}" is not between anim:{nm} markers (re-integration cannot replace it)',
               line_of(da[nm][0]))
    names = sorted(set(mk_names) | set(da))
    if starts and not any(i[0] == 'FAIL' and i[1] == 'markers' for i in R.items):
        R.ok('markers', f'{len(set(mk_names))} fragment(s) with paired markers: {", ".join(sorted(set(mk_names)))}')
    if not names:
        R.warn('markers', 'no anim-slides fragment found in the page')

    # ---- step control
    HS, HE = '<!-- anim-slides:step-host:start -->', '<!-- anim-slides:step-host:end -->'
    steps = [m for m in re.finditer(r'<[a-z][\w-]*\b[^>]*\sdata-anim-control\s*=\s*["\']step["\'][^>]*>', nocomment, re.I)]
    head_end = raw.lower().find('</head')
    h0 = raw.find(HS)
    host = h0 >= 0 and raw.find(HE, h0) > h0
    for m in steps:
        nm = re.search(r'''\sdata-anim\s*=\s*["']([\w-]+)''', m.group(0))
        nm = nm.group(1) if nm else '?'
        ph = re.search(r'''\sdata-anim-phases\s*=\s*["']([^"']*)["']''', m.group(0))
        if not ph or not ph.group(1).strip():
            R.fail('step', f'{nm}: data-anim-control="step" without data-anim-phases (the stop marks in seconds); '
                   'add it to the fragment and re-run integrate_fragment.py --control step', line_of(m.start()))
        else:
            R.ok('step', f'{nm}: step control, stops at {ph.group(1)} s')
    if steps and not host:
        R.fail('step', f'{len(steps)} step fragment(s) but no step host ({HS} ... end) in the page: the '
               'fragments would sit paused at 0; run integrate_fragment.py --control step', line_of(steps[0].start()))
    elif steps and head_end >= 0 and h0 > head_end:
        R.fail('step', 'the step host is outside <head>; it must come before the first fragment', line_of(h0))
    elif host and not steps:
        R.ok('step', 'step host present, no step fragment (it ignores once fragments)')
    for m in re.finditer(r'animSlides\.register\b', raw):
        R.fail('step', 'older script-driven step code (animSlides.register): fragments are CSS only now; '
               'remove it and the old host, then re-run integrate_fragment.py --control step', line_of(m.start()))
        break

    # ---- gate
    want = None if a.gate is None else a.gate.strip()
    if want is None and names:
        want, why = detect_gate(raw, names)
        if want:
            R.ok('gate', f'--gate not given: using "{want}" ({why}); pass --gate to override')
        else:
            R.warn('gate', '--gate not given and no host gate found in the page (no reveal.js, no script '
                   'adding "visible"): only checking that each fragment is gated')
    gates_seen = {}
    for nm in names:
        blk = re.search(r'<!--\s*anim-style:' + re.escape(nm) + r':start\s*-->(.*?)<!--\s*anim-style:'
                        + re.escape(nm) + r':end\s*-->', raw, re.S)
        if blk:
            off, chunk = blk.start(1), blk.group(1)
        else:   # unmarked fragment: look at every style block mentioning it
            off, chunk = 0, ''
            for m in re.finditer(r'<style\b[^>]*>(.*?)</style\s*>', raw, re.S | re.I):
                if f'.anim-{nm}' in m.group(1):
                    off, chunk = m.start(1), m.group(1)
                    break
        css_parts = [(off + m.start(1), m.group(1)) for m in re.finditer(r'<style\b[^>]*>(.*?)</style\s*>', chunk, re.S | re.I)] \
            if '<style' in chunk.lower() else [(off, chunk)]
        rules = []
        for o, c in css_parts:
            rules += list(animated_rules(parse_css(strip_css_comments(c), o)))
        if not rules:
            R.ok('gate', f'{nm}: no CSS animations (static)')
            continue
        root = f'.anim-{nm}'
        prefixes, bad = set(), []
        for sel, pos in rules:
            k = sel.find(root)
            pre = sel[:k].strip() if k >= 0 else None
            if pre is None:
                bad.append((sel, pos, 'does not target the fragment root'))
                continue
            prefixes.add(pre)
            if want is not None:
                if want.lower() == 'none':
                    continue
                if pre != want:
                    bad.append((sel, pos, f'gate is "{pre or "(none)"}", expected "{want}"'))
            elif not pre:
                bad.append((sel, pos, 'ungated: runs on every slide, also off screen'))
        for sel, pos, why in bad[:5]:
            R.fail('gate', f'{nm}: {sel[:90]}: {why}', line_of(pos))
        if len(bad) > 5:
            R.fail('gate', f'{nm}: {len(bad) - 5} more rule(s) with the same problem')
        if not bad:
            g = ', '.join(sorted(p or '(none)' for p in prefixes))
            R.ok('gate', f'{nm}: {len(rules)} animated rule(s) gated by {g}')
            gates_seen[nm] = g
    if want is None and len(set(gates_seen.values())) > 1:
        R.warn('gate', 'fragments use different gates: ' +
               '; '.join(f'{k}={v}' for k, v in sorted(gates_seen.items())))

    # ---- print guard
    for nm in names:
        pos, ok = print_guard(raw, nm)
        if ok:
            R.ok('print', f'{nm}: print guard sets animation: none (a PDF export shows the resting frame)')
        else:
            R.warn('print', f'{nm}: no print guard (@media print or html.print-pdf rule with animation: none); '
                   'a PDF export may show a mid-cycle frame: re-run integrate_fragment.py', line_of(pos))

    # ---- leftovers
    leftovers = [
        (r'virtual-time-budget', 'FAIL', 'headless render flag left in the page'),
        (r'animation-play-state\s*:\s*paused\s*!important', 'FAIL', 'render-phases pause style left in the page'),
        (r'<base\s[^>]*href\s*=\s*["\']?file:', 'FAIL', '<base href="file://..."> preview base left in the page'),
        (r'<!--\s*(?:scaffold|refine)\b', 'WARN', 'scaffold "refine by hand" note left in the page'),
        (r'(?<![\w-])preview-[\w-]+', 'WARN', 'preview- artefact name'),
    ]
    found = False
    lraw = raw   # the step host's own pause rule is intended: blank its block for this scan
    for m in re.finditer(re.escape(HS) + '.*?' + re.escape(HE), raw, re.S):
        lraw = lraw[:m.start()] + blank(m) + lraw[m.end():]
    for pat, lvl, why in leftovers:
        for m in re.finditer(pat, lraw, re.I):
            found = True
            (R.fail if lvl == 'FAIL' else R.warn)('leftovers', f'{why}: {m.group(0)[:60]!r}', line_of(m.start()))
    if not found:
        R.ok('leftovers', 'no preview or render artefacts')

    sys.exit(1 if R.print() else 0)


if __name__ == '__main__':
    main()
