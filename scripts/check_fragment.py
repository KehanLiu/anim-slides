#!/usr/bin/env python3
"""Static contract checks for an anim-slides fragment (references/fragment-contract.md).

Usage:
  check_fragment.py FRAGMENT.html --name NAME --rendered-width PX
                    [--stage-width W] [--min-text PX] [--gate .visible|none]
                    [--control once|loop|step]

  --rendered-width  width in CSS px at which the SVG is shown on the stage
  --stage-width     width of the host deck's slide stage in CSS px; sets the text floor to
                    18 * stage_width / 1920, never below 10 (12 at 1280, 10 at 960). When absent
                    a 1920 stage (floor 18 px) is assumed and an INFO line says so: pass the
                    host's real width (e.g. 1280) when its stage is narrower
  --min-text        explicit text floor in px; overrides the one derived from --stage-width
  --gate            ancestor selector that gates the animations (default .visible)
  --control         once | loop | step (default: the wrapper's data-anim-control, else once)

Controls (references/fragment-contract.md section 7):
  once  (default) one pass when the slide becomes current, then hold the finished state:
        data-anim-cycle 4-10 s, no `infinite`, every gated animation fills forwards/both,
        the 100 % keyframe equals the resting frame
  loop  continuous loop, only when asked for (kiosk, gallery, hero): cycle 8-15 s
  step  the presenter steps through the same one-pass fragment: the once rules plus
        data-anim-phases="<s>,<s>,..." on the wrapper (stop marks in seconds, strictly
        ascending, each > 0 and <= data-anim-cycle); the deck's step-host snippet drives it.
        On a once or loop wrapper data-anim-phases is optional and validated when present.
No control allows a <script> inside the fragment.
All controls: motion concurrency (things moving at the same instant, a staggered reveal counts
as one: WARN > 3, FAIL > 6) and
glow concurrency (glow elements visible at the same instant: WARN > 1, FAIL > 2; a stroke-only
glow warns: lines and arrows never glow).

Every finding is printed as OK / WARN / FAIL (INFO for notes) with a line hint. Exit code 1 on any FAIL.
Standard library only.
"""
import argparse
import math
import re
import sys
from html.parser import HTMLParser

TOKENS = ['--anim-bg', '--anim-panel', '--anim-line', '--anim-fg', '--anim-muted',
          '--anim-accent', '--anim-accent-2', '--anim-ok', '--anim-warn', '--anim-danger',
          '--anim-font', '--anim-mono']

NAMED_COLOURS = set("""
aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet
brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan
darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen
darkorange darkorchid darkred darksalmon darkseagreen darkslateblue darkslategray darkslategrey
darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite
forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow grey honeydew
hotpink indianred indigo ivory khaki lavender lavenderblush lawngreen lemonchiffon lightblue
lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon
lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime limegreen
linen magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen
mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose
moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen
paleturquoise palevioletred papayawhip peachpuff peru pink plum powderblue purple rebeccapurple
red rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue
slateblue slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet
wheat white whitesmoke yellow yellowgreen
""".split())

# properties / attributes whose values are colours (named colours are only checked here;
# hex, rgb() and hsl() are flagged in every value)
COLOUR_PROPS = re.compile(r'^(fill|stroke|color|stop-color|flood-color|lighting-color|caret-color|'
                          r'accent-color|background(-color)?|border(-\w+)*|outline(-color)?|'
                          r'box-shadow|text-shadow|filter|text-decoration(-color)?|column-rule(-color)?|--.*)$')
HEX = re.compile(r'#[0-9a-fA-F]{3,8}\b')
FUNC_COLOUR = re.compile(r'\b(rgba?|hsla?|hwb|lab|lch|oklab|oklch)\(', re.I)


# ----------------------------------------------------------------------------- reporting
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


# ----------------------------------------------------------------------------- markup
class Markup(HTMLParser):
    """Collects elements with attrs, line numbers, ancestors, and text outside <svg>."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elems = []          # dicts: tag, attrs, line, depth, ancestors(list of idx), in_svg
        self.stack = []          # indices into elems
        self.svg_depth = 0
        self.in_style = self.in_script = False
        self.outside_text = []   # (text, line)
        self.svg_texts = []
        self.styles = []         # (css, start line)
        self.scripts = []        # dict(attrs, line, after_svg)
        self.svg_closed = False
        self.cur_text_el = None

    VOID = {'meta', 'link', 'br', 'img', 'input', 'hr', 'source', 'wbr'}

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs, selfclosing=tag in self.VOID)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs, selfclosing=True)

    def _start(self, tag, attrs, selfclosing):
        line = self.getpos()[0]
        a = {k.lower(): (v if v is not None else '') for k, v in attrs}
        if tag == 'svg':
            self.svg_depth += 1
        el = dict(tag=tag, attrs=a, line=line, anc=list(self.stack), in_svg=self.svg_depth > 0, text='')
        self.elems.append(el)
        idx = len(self.elems) - 1
        if tag == 'style':
            self.in_style = True
            self.style_line = line
        if tag == 'script':
            self.in_script = True
            self.scripts.append(dict(attrs=a, line=line, after_svg=self.svg_closed, body=''))
        if not selfclosing:
            self.stack.append(idx)
        elif tag == 'svg':
            self.svg_depth -= 1
            self.svg_closed = True

    def handle_endtag(self, tag):
        if tag == 'style':
            self.in_style = False
        if tag == 'script':
            self.in_script = False
        if tag == 'svg' and self.svg_depth:
            self.svg_depth -= 1
            if self.svg_depth == 0:
                self.svg_closed = True
        # pop to the matching tag
        for i in range(len(self.stack) - 1, -1, -1):
            if self.elems[self.stack[i]]['tag'] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.in_style:
            self.styles.append((data, self.style_line))
            return
        if self.in_script:
            self.scripts[-1]['body'] += data
            return
        if not data.strip():
            return
        if self.svg_depth == 0:
            self.outside_text.append((data.strip(), self.getpos()[0]))
        elif self.stack:
            self.elems[self.stack[-1]]['text'] += data.strip()


# ----------------------------------------------------------------------------- css
def strip_comments(css):
    return re.sub(r'/\*.*?\*/', lambda m: re.sub(r'[^\n]', ' ', m.group(0)), css, flags=re.S)


def parse_css(css, base=0):
    """Return a list of nodes. rule: ('rule', selector, body, pos);
    at-rule with block: ('at', prelude, children_or_body, pos)."""
    nodes, i, n = [], 0, len(css)
    while i < n:
        j = css.find('{', i)
        semi = css.find(';', i)
        if j < 0:
            break
        if 0 <= semi < j and css[i:semi].strip().startswith('@'):  # @import x; etc.
            nodes.append(('atstmt', css[i:semi].strip(), '', base + i))
            i = semi + 1
            continue
        prelude = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            if css[k] == '{':
                depth += 1
            elif css[k] == '}':
                depth -= 1
            k += 1
        body = css[j + 1:k - 1]
        pos = base + i + (len(css[i:j]) - len(css[i:j].lstrip()))
        if prelude.startswith('@keyframes') or prelude.startswith('@-webkit-keyframes'):
            nodes.append(('keyframes', prelude.split(None, 1)[1].strip() if ' ' in prelude else '',
                          parse_css(body, base + j + 1), pos))
        elif prelude.startswith('@'):
            nodes.append(('at', prelude, parse_css(body, base + j + 1), pos))
        else:
            nodes.append(('rule', prelude, body, pos))
        i = k
    return nodes


def decls(body):
    out = []
    for d in body.split(';'):
        if ':' in d:
            p, v = d.split(':', 1)
            out.append((p.strip().lower(), v.strip()))
    return out


def walk_rules(nodes, ctx=()):
    """Yield (selector, body, pos, ctx) for ordinary rules, ctx = tuple of at-preludes."""
    for nd in nodes:
        if nd[0] == 'rule':
            yield nd[1], nd[2], nd[3], ctx
        elif nd[0] == 'at':
            yield from walk_rules(nd[2], ctx + (nd[1],))


def split_selectors(sel):
    return [s.strip() for s in sel.split(',') if s.strip()]


def last_compound_classes(sel):
    parts = re.split(r'\s+|>|\+|~', sel.strip())
    parts = [p for p in parts if p]
    return set(re.findall(r'\.([\w-]+)', parts[-1])) if parts else set()


# ----------------------------------------------------------------------------- selector matching
# A small matcher for the selectors fragments use: compounds of tag, #id and .class joined by
# descendant or child combinators. Anything else (pseudo-classes, attribute selectors, + and ~)
# makes the result None ("cannot tell"), so callers can stay conservative.
NO_RENDER = {'defs', 'clippath', 'mask', 'marker', 'symbol', 'pattern', 'lineargradient',
             'radialgradient', 'filter', 'style', 'script', 'title', 'desc', 'metadata'}


def parse_selector(sel):
    """Return ([(combinator, compound)], specificity) or (None, spec) when unsupported."""
    toks = re.findall(r'\s*([>+~])\s*|(\s+)|([^\s>+~]+)', sel.strip())
    out, comb = [], ' '
    ids = cls = tags = 0
    supported = True
    for c, ws, comp in toks:
        if c:
            comb = c
            continue
        if ws:
            continue
        m = re.fullmatch(r'(\*|[A-Za-z][\w-]*)?((?:[#.][\w-]+)*)(.*)', comp)
        tag, rest, tail = m.group(1), m.group(2), m.group(3)
        idl = re.findall(r'#([\w-]+)', rest)
        cll = re.findall(r'\.([\w-]+)', rest)
        ids += len(idl)
        cls += len(cll) + len(re.findall(r'[:\[]', tail))
        tags += 1 if tag and tag != '*' else 0
        if tail or comb in '+~':
            supported = False
        out.append((comb, dict(tag=None if tag in (None, '*') else tag.lower(), ids=idl, cls=set(cll))))
        comb = ' '
    return (out if supported else None), (ids, cls, tags)


def compound_matches(cp, el):
    if cp['tag'] and el['tag'] != cp['tag']:
        return False
    if cp['ids'] and el['attrs'].get('id') not in cp['ids']:
        return False
    return cp['cls'] <= set(el['attrs'].get('class', '').split())


def selector_matches(parsed, idx, E):
    """True / False for a parsed selector against element index idx."""
    def rec(k, i):
        comb, cp = parsed[k]
        if not compound_matches(cp, E[i]):
            return False
        if k == 0:
            return True
        anc = E[i]['anc']
        if comb == '>':
            return bool(anc) and rec(k - 1, anc[-1])
        return any(rec(k - 1, a) for a in reversed(anc))
    return rec(len(parsed) - 1, idx)


def css_number(v):
    v = v.replace('!important', '').strip()
    m = re.fullmatch(r'(-?\d*\.?\d+)(%?)', v)
    if not m:
        return None
    return float(m.group(1)) / (100 if m.group(2) else 1)


def time_s(v):
    m = re.search(r'(?<![\w.-])(\d*\.?\d+)(ms|s)\b', v)
    return None if not m else float(m.group(1)) / (1000 if m.group(2) == 'ms' else 1)


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split('\n', 2)[2])
    ap.add_argument('fragment')
    ap.add_argument('--name', required=True, help='fragment name (kebab-case, the anim-NAME class)')
    ap.add_argument('--rendered-width', type=float, required=True, metavar='PX',
                    help='width in CSS px at which the SVG is shown on the stage')
    ap.add_argument('--stage-width', type=float, default=None, metavar='W',
                    help='host slide stage width in CSS px (default: 1920 assumed); sets the text floor')
    ap.add_argument('--min-text', type=float, default=None, metavar='PX',
                    help='explicit text floor in px; overrides the one derived from --stage-width')
    ap.add_argument('--gate', default='.visible', help='gate selector, or "none"')
    ap.add_argument('--control', choices=['once', 'loop', 'step'], default=None)
    a = ap.parse_args()
    stage_assumed = a.stage_width is None and a.min_text is None
    if a.stage_width is None:
        a.stage_width = 1920.0
    if a.min_text is None:
        a.min_text = round(max(10.0, 18 * a.stage_width / 1920), 2)
        floor_src = f'18 px x {a.stage_width:g}/1920 stage' + (', clamped to 10' if a.min_text == 10 else '')
    else:
        floor_src = '--min-text'

    src = open(a.fragment, encoding='utf-8').read()
    name, pref = a.name, a.name + '-'
    wrap_cls = f'anim-{name}'
    gate = None if a.gate.strip().lower() == 'none' else a.gate.strip()
    gate_classes = set(re.findall(r'\.([\w-]+)', gate)) if gate else set()
    R = Report()
    if stage_assumed:
        R.add('INFO', 'text-size', f'no --stage-width given: assuming a {a.stage_width:g} px stage, text floor '
              f'{a.min_text:g} px; pass --stage-width W if the host stage is narrower')

    if not re.fullmatch(r'[a-z][a-z0-9]*(-[a-z0-9]+)*', name) or not 2 <= len(name) <= 24:
        R.fail('structure', f'name "{name}" must be kebab-case, 2-24 chars')

    def line_of(pos):
        return src.count('\n', 0, pos) + 1

    mk = Markup()
    mk.feed(src)
    mk.close()
    E = mk.elems

    # ------------------------------------------------------------------ structure
    styles = [e for e in E if e['tag'] == 'style']
    if len(styles) != 1:
        R.fail('structure', f'expected exactly 1 <style>, found {len(styles)}')
    css_raw = ''.join(s for s, _ in mk.styles)
    style_pos = src.find('>', src.find('<style')) + 1 if '<style' in src else 0
    css = strip_comments(css_raw)

    roots = [e for e in E if e['tag'] == 'div' and not e['anc']]
    wrappers = [e for e in E if e['tag'] == 'div'
                and {'anim', wrap_cls} <= set(e['attrs'].get('class', '').split())]
    if len(wrappers) != 1:
        R.fail('structure', f'expected one <div class="anim {wrap_cls}">, found {len(wrappers)}')
    wrapper = wrappers[0] if wrappers else None
    if wrapper and wrapper['anc']:
        R.fail('structure', 'wrapper div must be top level, not nested', wrapper['line'])
    if len(roots) > 1:
        R.fail('structure', f'{len(roots)} top-level <div>s; only the wrapper is allowed', roots[1]['line'])
    others = [e for e in E if not e['anc'] and e['tag'] not in ('style', 'div', 'script')]
    for e in others:
        R.fail('structure', f'unexpected top-level <{e["tag"]}>', e['line'])
    control = a.control
    ctl_implicit = False
    if wrapper:
        wa = wrapper['attrs']
        if wa.get('data-anim') != name:
            R.fail('structure', f'wrapper needs data-anim="{name}"', wrapper['line'])
        cyc = wa.get('data-anim-cycle')
        if cyc is None:
            R.fail('structure', 'wrapper needs data-anim-cycle="<seconds>"', wrapper['line'])
        elif not re.fullmatch(r'\d+(\.\d+)?', cyc.strip()):
            R.fail('structure', f'data-anim-cycle="{cyc}" is not numeric', wrapper['line'])
        ctl = wa.get('data-anim-control')
        ctl_implicit = ctl is None and not control
        ctl = ctl or 'once'
        if ctl not in ('once', 'loop', 'step'):
            R.fail('structure', f'data-anim-control="{ctl}" must be once, loop or step', wrapper['line'])
            ctl = 'once'
        control = control or ctl
        lo, hi = {'once': (4, 10), 'step': (4, 10), 'loop': (8, 15)}.get(control, (None, None))
        if lo and cyc and re.fullmatch(r'\d+(\.\d+)?', cyc.strip()) and not lo <= float(cyc) <= hi:
            R.fail('structure', f'data-anim-cycle="{cyc}" outside {lo} to {hi} s for control={control} '
                   '(contract section 6)' + (' (data-anim-control absent, so once is assumed; set '
                   'data-anim-control="once" and shorten the pass, or "loop" only for a kiosk/gallery/hero)'
                   if ctl_implicit else ''), wrapper['line'])
    control = control or 'once'

    # data-anim-phases: stop marks for step control (required there, validated wherever present)
    phases = wrapper['attrs'].get('data-anim-phases') if wrapper else None
    phase_marks = None
    if wrapper and phases is None and control == 'step':
        R.fail('structure', 'control=step needs data-anim-phases="<s>,<s>,..." on the wrapper: the stop '
               'marks in seconds (segment k runs from mark k-1, 0 for the first, to mark k)', wrapper['line'])
    elif wrapper and phases is not None:
        toks = [t.strip() for t in phases.split(',')]
        cyc = wrapper['attrs'].get('data-anim-cycle', '').strip()
        cycv = float(cyc) if re.fullmatch(r'\d+(\.\d+)?', cyc) else None
        if not all(re.fullmatch(r'\d+(\.\d+)?|\.\d+', t) for t in toks):
            R.fail('structure', f'data-anim-phases="{phases}" must be comma-separated seconds, e.g. "2,4.5,7"',
                   wrapper['line'])
        else:
            marks = [float(t) for t in toks]
            if any(m <= 0 for m in marks):
                R.fail('structure', f'data-anim-phases="{phases}": every mark must be > 0 (0 is the implicit start)',
                       wrapper['line'])
            if any(b <= a for a, b in zip(marks, marks[1:])):
                R.fail('structure', f'data-anim-phases="{phases}" must be strictly ascending', wrapper['line'])
            if cycv is not None and marks[-1] > cycv + 1e-9:
                R.fail('structure', f'data-anim-phases="{phases}": mark {marks[-1]:g} is past the pass '
                       f'(data-anim-cycle="{cyc}")', wrapper['line'])
            phase_marks = marks

    svgs = [e for e in E if e['tag'] == 'svg']
    vbw = None
    if len(svgs) != 1:
        R.fail('structure', f'expected exactly 1 <svg>, found {len(svgs)}')
    if svgs:
        sv = svgs[0]
        if wrapper and E.index(wrapper) not in sv['anc']:
            R.fail('structure', '<svg> must be inside the wrapper div', sv['line'])
        vb = sv['attrs'].get('viewbox', '')
        nums = re.split(r'[\s,]+', vb.strip())
        try:
            vbw = float(nums[2]) if len(nums) == 4 else None
        except ValueError:
            vbw = None
        if not vbw:
            R.fail('structure', 'svg needs viewBox="0 0 W H"', sv['line'])
        if sv['attrs'].get('role') != 'img' or not sv['attrs'].get('aria-label', '').strip():
            R.warn('structure', 'svg should have role="img" and a non-empty aria-label', sv['line'])
    for t, ln in mk.outside_text:
        R.fail('structure', f'HTML text outside the SVG: "{t[:40]}"', ln)
    for e in E:
        if not e['in_svg'] and e['tag'] not in ('style', 'div', 'script', 'svg'):
            R.fail('structure', f'HTML element <{e["tag"]}> outside the SVG', e['line'])
    if not any(i[0] == 'FAIL' and i[1] == 'structure' for i in R.items):
        R.ok('structure', f'one <style>, wrapper div.anim.{wrap_cls}, one <svg> (viewBox width {vbw:g}), control={control}'
              + (' (default: no data-anim-control)' if ctl_implicit else ''))

    # ------------------------------------------------------------------ forbidden
    nf0 = len(R.items)
    scripts = mk.scripts
    for s in scripts:
        R.fail('forbidden', f'<script> not allowed in a fragment (control={control})'
               + ('; step is driven by the deck\'s step-host snippet, the fragment stays CSS only'
                  if control == 'step' else ''), s['line'])
    for e in E:
        if e['tag'] in ('link', 'image', 'img', 'iframe', 'object', 'embed', 'foreignobject'):
            R.fail('forbidden', f'<{e["tag"]}> not allowed', e['line'])
        for k in ('href', 'xlink:href', 'src'):
            v = e['attrs'].get(k)
            if v is not None and e['tag'] != 'script' and not v.startswith('#'):
                R.fail('forbidden', f'{k}="{v[:40]}" points outside the fragment', e['line'])
    for kw in ('@import', '@font-face'):
        for m in re.finditer(re.escape(kw), css):
            R.fail('forbidden', f'{kw} not allowed', line_of(style_pos + m.start()))
    markup_only = re.sub(r'<(style|script)\b.*?</\1>', lambda m: re.sub(r'[^\n]', ' ', m.group(0)), src, flags=re.S | re.I)
    for text, base in ((css, style_pos), (markup_only, 0)):
        for m in re.finditer(r'url\(\s*([\'"]?)([^)\'"]*)\1\s*\)', text):
            if not m.group(2).startswith('#'):
                R.fail('forbidden', f'url({m.group(2)[:40]}) points outside the fragment',
                       line_of(base + m.start()) if base else line_of(m.start()))
    if len(R.items) == nf0:
        R.ok('forbidden', 'no external resources, no script')

    # ------------------------------------------------------------------ namespacing
    nf0 = len(R.items)
    exempt = {'anim', wrap_cls} | gate_classes
    markup_classes = set()
    for e in E:
        for c in e['attrs'].get('class', '').split():
            markup_classes.add(c)
            if c not in exempt and not c.startswith(pref):
                R.fail('namespacing', f'class "{c}" not prefixed {pref}', e['line'])
        i = e['attrs'].get('id')
        if i is not None and not i.startswith(pref):
            R.fail('namespacing', f'id "{i}" not prefixed {pref}', e['line'])
    tree = parse_css(css)
    gate_re = re.escape(gate) + r'\s+' if gate else None
    wrap_re = r'\.' + re.escape(wrap_cls) + r'(?![\w-])'

    def check_kf(nodes):
        for nd in nodes:
            if nd[0] == 'keyframes':
                if not nd[1].startswith(pref):
                    R.fail('namespacing', f'@keyframes "{nd[1]}" not prefixed {pref}', line_of(style_pos + nd[3]))
            elif nd[0] == 'at':
                check_kf(nd[2])
    check_kf(tree)
    for sel, body, pos, ctx in walk_rules(tree):
        ln = line_of(style_pos + pos)
        for s in split_selectors(sel):
            ok = re.match(wrap_re, s) or (gate_re and re.match(gate_re + wrap_re, s))
            if not ok:
                R.fail('namespacing', f'selector "{s[:60]}" must start with .{wrap_cls}'
                       + (f' or "{gate} .{wrap_cls}"' if gate else ''), ln)
            for c in re.findall(r'\.([A-Za-z_][\w-]*)', s):
                if c not in exempt and not c.startswith(pref):
                    R.fail('namespacing', f'selector class ".{c}" not prefixed {pref}', ln)
            for i in re.findall(r'#([A-Za-z_][\w-]*)', s):
                if not i.startswith(pref):
                    R.fail('namespacing', f'selector id "#{i}" not prefixed {pref}', ln)
    if len(R.items) == nf0:
        R.ok('namespacing', f'all classes, ids, keyframes and selectors prefixed ({len(markup_classes)} classes)')

    # ------------------------------------------------------------------ theme tokens
    nf0 = len(R.items)
    token_rules = [(b, p) for s, b, p, ctx in walk_rules(tree)
                   if not ctx and any(x == f'.{wrap_cls}' for x in split_selectors(s))]
    defined = set()
    for b, p in token_rules:
        defined |= {k for k, v in decls(b) if k.startswith('--anim-')}
    missing = [t for t in TOKENS if t not in defined]
    if missing:
        R.fail('tokens', f'wrapper rule .{wrap_cls} must define {", ".join(missing)}')

    def colour_issue(prop, value):
        v = re.sub(r'url\([^)]*\)', '', value)
        v = re.sub(r'var\(\s*--[\w-]+', 'var(', v)
        if HEX.search(v):
            return f'hex colour {HEX.search(v).group(0)}'
        if FUNC_COLOUR.search(v):
            return f'{FUNC_COLOUR.search(v).group(1)}() colour'
        if COLOUR_PROPS.match(prop):
            for w in re.findall(r'(?<![\w-])([A-Za-z]+)(?![\w(-])', v):
                if w.lower() in NAMED_COLOURS:
                    return f'named colour "{w}"'
        return None

    def check_decls(body, pos, in_token_rule):
        for prop, val in decls(body):
            if in_token_rule and prop.startswith('--anim-'):
                continue
            iss = colour_issue(prop, val)
            if iss:
                R.fail('tokens', f'{iss} in "{prop}: {val[:50]}" (use var(--anim-*))', line_of(style_pos + pos))

    def walk_all(nodes, ctx_kf=False):
        for nd in nodes:
            if nd[0] == 'rule':
                is_tok = (not ctx_kf) and any(x == f'.{wrap_cls}' for x in split_selectors(nd[1]))
                check_decls(nd[2], nd[3], is_tok)
            elif nd[0] in ('at', 'keyframes'):
                walk_all(nd[2], ctx_kf or nd[0] == 'keyframes')
    walk_all(tree)
    for e in E:
        for k, v in e['attrs'].items():
            if k == 'style':
                for prop, val in decls(v):
                    iss = colour_issue(prop, val)
                    if iss:
                        R.fail('tokens', f'{iss} in style="{prop}: {val[:40]}"', e['line'])
            elif k in ('fill', 'stroke', 'stop-color', 'flood-color', 'lighting-color', 'color'):
                iss = colour_issue(k, v)
                if iss:
                    R.fail('tokens', f'{iss} in {k}="{v}"', e['line'])
    if len(R.items) == nf0:
        R.ok('tokens', f'all {len(TOKENS)} --anim-* tokens defined; no literal colours outside the token block')

    # ------------------------------------------------------------------ gating
    nf0 = len(R.items)
    anim_rules = []   # (selector, value, line, gated)
    for sel, body, pos, ctx in walk_rules(tree):
        for prop, val in decls(body):
            if prop in ('animation', 'animation-name'):
                v = val.replace('!important', '').strip()
                if v.lower() == 'none':
                    continue
                for s in split_selectors(sel):
                    gated = bool(gate_re and re.match(gate_re, s))
                    anim_rules.append((s, v, line_of(style_pos + pos), gated, ctx))
    if gate:
        for s, v, ln, g, ctx in anim_rules:
            if not g:
                R.warn('gating', f'animation not under "{gate}": {s[:60]}', ln)
        if anim_rules and not any(r[3] for r in anim_rules):
            R.fail('gating', f'no animation rule is gated by "{gate}"')
        elif not anim_rules:
            R.warn('gating', 'no CSS animations found')
        if len(R.items) == nf0:
            R.ok('gating', f'{len(anim_rules)} animation rule(s), all under "{gate}"')
    else:
        R.ok('gating', f'--gate none: {len(anim_rules)} animation rule(s) run always')

    # ------------------------------------------------------------------ reduced motion
    rm = [nd for nd in tree if nd[0] == 'at' and 'prefers-reduced-motion' in nd[1] and 'reduce' in nd[1]]
    if rm:
        R.ok('reduced-motion', '@media (prefers-reduced-motion: reduce) block present')
    else:
        R.fail('reduced-motion', f'missing @media (prefers-reduced-motion: reduce) {{ .{wrap_cls} * {{ animation: none !important; }} }}')

    # ------------------------------------------------------------------ text size
    nf0 = len(R.items)
    sizes = []
    unverified = []
    if vbw:
        scale = a.rendered_width / vbw

        def check_size(val, where, ln):
            m = re.search(r'(\d+(?:\.\d+)?)\s*(px)?(?![\w%])', val)
            if not m or re.search(r'\d\s*(em|rem|%|pt|vw|vh)\b', val):
                unverified.append((where, val, ln))
                return
            px = float(m.group(1))
            sizes.append(px * scale)
            if px * scale < a.min_text - 0.01:
                R.fail('text-size', f'{where} {px:g}px renders at {px * scale:.1f}px < {a.min_text:g}px'
                       + (f' (floor for an assumed {a.stage_width:g} px stage; pass --stage-width W if the '
                          'host stage is narrower)' if stage_assumed else ''), ln)

        for sel, body, pos, ctx in walk_rules(tree):
            for prop, val in decls(body):
                if prop == 'font-size':
                    check_size(val, f'css "{sel[:40]}" font-size', line_of(style_pos + pos))
                elif prop == 'font':
                    m = re.search(r'(\d+(?:\.\d+)?)px', val)
                    if m:
                        check_size(m.group(0), f'css "{sel[:40]}" font', line_of(style_pos + pos))
        for e in E:
            if 'font-size' in e['attrs']:
                check_size(e['attrs']['font-size'], f'<{e["tag"]} font-size>', e['line'])
            for prop, val in decls(e['attrs'].get('style', '')):
                if prop == 'font-size':
                    check_size(val, f'<{e["tag"]} style font-size>', e['line'])
        for where, val, ln in unverified:
            R.warn('text-size', f'cannot verify relative size "{val}" ({where})', ln)
        # text elements that never get a size inherit the host's font-size
        fs_classes, fs_types = set(), False
        for sel, body, pos, ctx in walk_rules(tree):
            if any(p in ('font-size', 'font') for p, _ in decls(body)):
                for s in split_selectors(sel):
                    fs_classes |= set(re.findall(r'\.([\w-]+)', s.split()[-1])) - {wrap_cls}
                    if re.search(r'(^|\s)(text|tspan|svg)\b', s) or re.fullmatch(wrap_re, s.strip()):
                        fs_types = True
        if not fs_types:
            for e in E:
                if e['tag'] != 'text':
                    continue
                chain = [E[i] for i in e['anc']] + [e]
                if not any('font-size' in x['attrs'] or 'font-size' in x['attrs'].get('style', '')
                           or set(x['attrs'].get('class', '').split()) & fs_classes for x in chain):
                    R.warn('text-size', '<text> without any font-size inherits the host size', e['line'])
        title_min = a.min_text * 22 / 18
        if sizes and max(sizes) < title_min - 0.01:
            R.warn('text-size', f'largest text renders at {max(sizes):.1f}px < {title_min:.3g}px: fine without a '
                   'title, otherwise titles must reach the title floor (contract section 6)')
        R.ok('text-size', f'floor {a.min_text:g}px ({floor_src}), title floor {title_min:.3g}px')
        if len(R.items) == nf0 + 1:
            R.ok('text-size', f'{len(sizes)} sizes, smallest {min(sizes):.1f}px at {a.rendered_width:g}px wide'
                 f' (min {a.min_text:g})' if sizes else 'no explicit font sizes')

    # ------------------------------------------------------------------ resting frame
    # The resting frame is the ungated state (contract section 5). An element with no base
    # opacity rule rests at opacity 1, so keyframes that end at 0 to reset the loop are fine.
    # Warn only when the base state explicitly hides an element (opacity 0, visibility hidden,
    # display none) that the story shows at its end, or a label that nothing ever reveals.
    nf0 = len(R.items)
    cycle = None
    if wrapper and re.fullmatch(r'\d+(\.\d+)?', (wrapper['attrs'].get('data-anim-cycle') or '').strip()):
        cycle = float(wrapper['attrs']['data-anim-cycle'])

    keyframes = {}   # name -> [(pct, {prop: value})]

    def collect_kf(nodes):
        for nd in nodes:
            if nd[0] == 'keyframes':
                stops = []
                for k in nd[2]:
                    if k[0] != 'rule':
                        continue
                    dd = dict(decls(k[2]))
                    for x in k[1].split(','):
                        x = x.strip().lower()
                        pct = 0.0 if x == 'from' else 100.0 if x == 'to' else \
                            float(x[:-1]) if re.fullmatch(r'\d*\.?\d+%', x) else None
                        if pct is not None:
                            stops.append((pct, dd))
                keyframes[nd[1]] = sorted(stops, key=lambda t: t[0])
            elif nd[0] == 'at':
                collect_kf(nd[2])
    collect_kf(tree)

    def strip_gate(s):
        return re.sub('^' + gate_re, '', s) if gate_re and re.match(gate_re, s) else s

    # base (ungated, outside @media) declarations of the three hiding properties
    HIDE_PROPS = ('opacity', 'visibility', 'display', 'fill')   # fill: for the glow-on-a-line check
    base_rules = []   # (parsed, spec, order, {prop: (value, important)})
    order = 0
    for sel, body, pos, ctx in walk_rules(tree):
        order += 1
        dd = {p: (v.replace('!important', '').strip(), '!important' in v)
              for p, v in decls(body) if p in HIDE_PROPS}
        if ctx or not dd:
            continue
        for s in split_selectors(sel):
            if gate_re and re.match(gate_re, s):
                continue
            parsed, spec = parse_selector(s)
            if parsed:
                base_rules.append((parsed, spec, order, dd))

    def resolved(i, prop):
        el = E[i]
        best = None   # key, value
        if prop in el['attrs']:
            best = ((0, 0, (-1, 0, 0), 0), el['attrs'][prop].strip())
        for parsed, spec, o, dd in base_rules:
            if prop in dd and selector_matches(parsed, i, E):
                v, imp = dd[prop]
                key = (int(imp), 1, spec, o)
                if best is None or key > best[0]:
                    best = (key, v)
        for p, v in decls(el['attrs'].get('style', '')):
            if p == prop:
                key = (int('!important' in v), 2, (0, 0, 0), 0)
                if best is None or key > best[0]:
                    best = (key, v.replace('!important', '').strip())
        return best[1] if best else None

    def hidden_at_rest(i):
        op = resolved(i, 'opacity')
        opn = css_number(op) if op else None
        if opn is not None and opn <= 0.01:
            return f'opacity: {op}'
        if (resolved(i, 'visibility') or '').lower() in ('hidden', 'collapse'):
            return 'visibility: hidden'
        if (resolved(i, 'display') or '').lower() == 'none':
            return 'display: none'
        return None

    # animations per element: idx -> [(keyframe names, duration s)]; unsure = matched only loosely
    anims, unsure = {}, set()
    for sel, body, pos, ctx in walk_rules(tree):
        dd = decls(body)
        vals = [v for p, v in dd if p in ('animation', 'animation-name')]
        if ctx or not vals:
            continue
        dur = next((time_s(v) for p, v in dd if p == 'animation-duration'), None)
        for v in vals:
            names = set(re.findall(r'(?<![\w-])([A-Za-z_][\w-]*)', v)) & set(keyframes)
            if not names:
                continue
            d = time_s(v) if time_s(v) is not None else dur
            for s in split_selectors(sel):
                s2 = strip_gate(s)
                parsed, _ = parse_selector(s2)
                want = last_compound_classes(s2)
                for i, e in enumerate(E):
                    if parsed is None:
                        if want and want <= set(e['attrs'].get('class', '').split()):
                            unsure.add(i)
                    elif selector_matches(parsed, i, E):
                        anims.setdefault(i, []).append((names, d))

    def visible_at(stops, prop, p, base_hidden_value):
        """Opacity (float) or visibility (bool) of a keyframe track at p percent."""
        pts = [(pct, dd[prop]) for pct, dd in stops if prop in dd]
        if not pts:
            return None
        if prop == 'visibility':
            cur = None
            for pct, v in pts:
                if pct <= p:
                    cur = v.replace('!important', '').strip().lower()
            return None if cur is None else cur == 'visible'
        pts = [(pct, css_number(v)) for pct, v in pts]
        if any(v is None for _, v in pts):
            return None
        if pts[0][0] > 0:
            pts.insert(0, (0.0, base_hidden_value))
        if pts[-1][0] < 100:
            pts.append((100.0, base_hidden_value))
        for (p0, v0), (p1, v1) in zip(pts, pts[1:]):
            if p0 <= p <= p1:
                return max(v0, v1) if p1 == p0 else v0 + (v1 - v0) * (p - p0) / (p1 - p0)
        return None

    def has_text(i):
        if E[i]['tag'] in ('text', 'tspan', 'textpath'):
            return True
        return any(e['tag'] in ('text', 'tspan', 'textpath') and i in e['anc'] for e in E)

    # A hidden element with a visible sibling of the same shape and text is a highlight overlay
    # (the lit copy of a step, a wire, a label): the resting frame still shows the content.
    GEOM = ('d', 'x', 'y', 'cx', 'cy', 'r', 'rx', 'ry', 'width', 'height', 'points',
            'x1', 'y1', 'x2', 'y2', 'transform', 'href', 'xlink:href')
    kids = {}
    for i, e in enumerate(E):
        if e['anc']:
            kids.setdefault(e['anc'][-1], []).append(i)

    def shape(i):
        e = E[i]
        return (e['tag'], tuple(e['attrs'].get(k) for k in GEOM), e['text'],
                tuple(shape(c) for c in kids.get(i, [])))

    def has_visible_twin(i):
        par = E[i]['anc'][-1] if E[i]['anc'] else None
        sib = kids.get(par, []) if par is not None else []
        me = shape(i)
        return any(j != i and shape(j) == me and not hidden_at_rest(j) for j in sib)

    shown_late, never_shown = [], []
    for i, e in enumerate(E):
        if not e['in_svg'] or e['tag'] in NO_RENDER or any(E[a]['tag'] in NO_RENDER for a in e['anc']):
            continue
        why = hidden_at_rest(i)
        if not why or has_visible_twin(i):
            continue
        tracks = anims.get(i, [])
        late = None
        for names, d in tracks:
            d = d or cycle
            if not d or (cycle and d < 0.75 * cycle):
                continue   # short decorative loop (pulse, spinner), not the story track
            # loop: one second before the loop restarts (the hold); once: the end of the pass
            p = 100.0 if control in ('once', 'step') else max(50.0, 100 * (1 - 1 / d))
            for nm in names:
                prop = 'visibility' if why.startswith('visibility') else 'opacity'
                v = visible_at(keyframes[nm], prop, p, 0.0)
                if (v is True) or (isinstance(v, float) and v > 0.01):
                    late = (nm, p)
        if late:
            shown_late.append((e, why, late))
        elif not tracks and i not in unsure and has_text(i):
            never_shown.append((e, why))

    def describe(e):
        c = e['attrs'].get('class', '').strip()
        return f'<{e["tag"]}' + (f' class="{c}"' if c else '') + (f' id="{e["attrs"]["id"]}"' if 'id' in e['attrs'] else '') + '>'
    for e, why, (nm, p) in shown_late:
        R.warn('resting-frame', f'{describe(e)} rests hidden ({why}) but keyframes {nm} show it at the '
               f'end of the story ({p:.0f}%): PDF and reduced-motion show it missing; put the end state '
               'in the base rule and start the keyframes from hidden', e['line'])
    for e, why in never_shown:
        R.warn('resting-frame', f'{describe(e)} contains text, rests hidden ({why}) and no animation '
               'reveals it', e['line'])
    # a finite animation with fill forwards/both that ends at opacity 0 leaves the element
    # invisible for as long as the slide is shown
    for s, v, ln, g, ctx in (anim_rules if control == 'loop' else []):   # once/step: see the control section
        if ctx or re.search(r'\binfinite\b', v) or not re.search(r'\b(forwards|both)\b', v):
            continue
        for nm in set(re.findall(r'(?<![\w-])([A-Za-z_][\w-]*)', v)) & set(keyframes):
            end = [dd for pct, dd in keyframes[nm] if pct == 100.0 and 'opacity' in dd]
            if end and (css_number(end[-1]['opacity']) or 0) <= 0.01:
                R.warn('resting-frame', f'finite animation {nm} with fill forwards ends at opacity 0: '
                       f'{s[:60]} stays invisible once played', ln)
    if len(R.items) == nf0:
        R.ok('resting-frame', 'no element that the story shows at its end is hidden in the resting frame')

    # ------------------------------------------------------------------ control: once / step
    # once (default): one pass, then hold the finished state. No infinite, every gated animation
    # fills forwards/both, and each track ends (100 %) on the resting frame. step is the same
    # fragment, paused at the data-anim-phases marks by the deck's step host.
    if control in ('once', 'step'):
        nf0 = len(R.items)
        why = (' (data-anim-control absent, so once is assumed)' if ctl_implicit else '')
        fix = ('use animation-iteration-count 1 (drop infinite) with animation-fill-mode forwards and make '
               'the 100 % keyframe the resting frame; set data-anim-control="loop" only for a kiosk, '
               'gallery or hero loop (contract section 7)')
        inf = [m.start() for m in re.finditer(r'\binfinite\b', css)]
        if inf:
            R.fail('control', f'control={control}{why}: {len(inf)} "infinite" in the style; the fragment must play '
                   f'once and rest: {fix}', line_of(style_pos + inf[0]))
        fill_rules = set()
        for sel, body, pos, ctx in walk_rules(tree):
            for prop, val in decls(body):
                if prop == 'animation-fill-mode' and re.search(r'\b(forwards|both)\b', val):
                    fill_rules |= set(split_selectors(sel))
        any_fill_decl = any(x.rstrip().endswith('*') for x in fill_rules)   # e.g. .visible .anim-x * {...}
        nofill, many = [], []
        for s, v, ln, g, ctx in anim_rules:
            if ctx or (gate and not g):
                continue
            if not re.search(r'\b(forwards|both)\b', v) and s not in fill_rules and not any_fill_decl:
                nofill.append((s, ln))
            bare = re.sub(r'\([^)]*\)', '', v)
            for n in re.findall(r'(?<![\w.%-])(\d*\.?\d+)(?![\w.%])', bare):
                if float(n) > 1:
                    many.append((s, ln, n))
        if nofill:
            R.fail('control', f'control={control}{why}: {len(nofill)} gated animation(s) without fill-mode forwards/both '
                   f'(first: {nofill[0][0][:50]}); after the pass the element snaps back: {fix}', nofill[0][1])
        for s, ln, n in many[:3]:
            R.fail('control', f'control={control}: iteration count {n} on {s[:50]}; one pass only', ln)
        # each track's last opacity must equal the resting opacity
        ends = []
        for i, tracks in anims.items():
            if i in unsure:
                continue
            for names, d in tracks:
                for nm in names:
                    pts = [(pct, dd['opacity']) for pct, dd in keyframes.get(nm, []) if 'opacity' in dd]
                    if not pts or pts[-1][0] < 100.0:
                        continue    # no 100 % stop: the browser ends on the base value, i.e. the resting frame
                    end = css_number(pts[-1][1])
                    rest = resolved(i, 'opacity')
                    restn = 1.0 if rest is None else css_number(rest)
                    if end is not None and restn is not None and abs(end - restn) > 0.01:
                        ends.append((E[i], nm, end, restn))
        for e, nm, end, restn in ends[:5]:
            R.warn('control', f'{describe(e)}: keyframes {nm} end at opacity {end:g} but the resting frame has '
                   f'{restn:g}; the 100 % keyframe must equal the resting frame', e['line'])
        if len(R.items) == nf0:
            R.ok('control', f'{control}: no infinite, gated animations fill forwards/both, tracks end on the resting frame'
                 + (f'; stops at {phases} s' if control == 'step' and phases else ''))
    elif control == 'loop':
        R.ok('control', 'loop: continuous; use only when a loop was asked for (kiosk, gallery, hero)')

    # ------------------------------------------------------------------ motion and glow concurrency
    # The eye sees moving parts, not tracks: sample the pass and count how many elements are
    # moving at the same instant, and how many glow elements are visible at the same instant.
    def split_top(v):
        out, depth, cur = [], 0, ''
        for ch in v:
            depth += ch == '('
            depth -= ch == ')'
            if ch == ',' and depth == 0:
                out.append(cur)
                cur = ''
            else:
                cur += ch
        return [x.strip() for x in out + [cur] if x.strip()]

    def parse_anim(entry, longs, k):
        nm = (set(re.findall(r'(?<![\w-])([A-Za-z_][\w-]*)', entry)) & set(keyframes))
        if not nm:
            return None
        bare = re.sub(r'\([^)]*\)', '', entry)
        times = [float(m.group(1)) / (1000 if m.group(2) == 'ms' else 1)
                 for m in re.finditer(r'(?<![\w.-])(-?\d*\.?\d+)(ms|s)\b', bare)]
        def lg(prop):
            vals = split_top(longs.get(prop, ''))
            return vals[min(k, len(vals) - 1)] if vals else None
        dur = times[0] if times else time_s(lg('animation-duration') or '')
        delay = times[1] if len(times) > 1 else (time_s(lg('animation-delay') or '') if lg('animation-delay') else 0.0)
        it = lg('animation-iteration-count')
        if re.search(r'\binfinite\b', bare) or (it and 'infinite' in it):
            iters = math.inf
        else:
            m = re.search(r'(?<![\w.%-])(\d*\.?\d+)(?![\w.%])', bare)
            iters = float(m.group(1)) if m else (float(it) if it and re.fullmatch(r'\d*\.?\d+', it) else 1.0)
        fm = re.search(r'\b(forwards|backwards|both|none)\b', bare)
        fill = fm.group(1) if fm else (lg('animation-fill-mode') or 'none')
        if not dur or dur <= 0:
            return None
        return {'name': sorted(nm)[0], 'dur': dur, 'delay': max(0.0, delay or 0.0), 'iters': iters, 'fill': fill}

    tracks = {}      # element index -> [track]
    for sel, body, pos, ctx in walk_rules(tree):
        if ctx:
            continue
        dd = decls(body)
        longs = {p: v for p, v in dd if p.startswith('animation-')}
        for p, v in dd:
            if p not in ('animation', 'animation-name'):
                continue
            v = v.replace('!important', '').strip()
            if v.lower() == 'none':
                continue
            parsed_tr = [t for t in (parse_anim(x, longs, k) for k, x in enumerate(split_top(v))) if t]
            if not parsed_tr:
                continue
            for s1 in split_selectors(sel):
                if gate and not (gate_re and re.match(gate_re, s1)):
                    pass     # ungated animations also run while shown
                parsed, _ = parse_selector(strip_gate(s1))
                if parsed is None:
                    continue
                for i in range(len(E)):
                    if selector_matches(parsed, i, E):
                        tracks.setdefault(i, []).extend(parsed_tr)

    def kf_moving(name):
        """[(p0, p1, kind)] in 0..1 where keyframes `name` change something. Each property is
        followed on its own (CSS interpolates a property between the stops that name it, so a
        stop that omits it changes nothing). kind: 'appear' = opacity rises from 0, optionally
        with a transform settling, and nothing else changes; 'fade' = another opacity-only
        change; 'action' = anything else."""
        per = {}
        for pct, d in keyframes.get(name, []):
            for k, v in d.items():
                if k != 'animation-timing-function':
                    per.setdefault(k, []).append((pct / 100, v))
        segs_p = []    # (p0, p1, prop, rising_from_zero)
        for k, pts in per.items():
            for (a, va), (b, vb) in zip(pts, pts[1:]):
                if b > a and va != vb:
                    n0, n1 = css_number(va), css_number(vb)
                    segs_p.append((a, b, k, k == 'opacity' and n0 is not None and n1 is not None
                                   and n0 <= 0.01 and n1 > n0))
        cuts = sorted({x for a, b, _, _ in segs_p for x in (a, b)})
        out = []
        for a, b in zip(cuts, cuts[1:]):
            act = [sp for sp in segs_p if sp[0] <= a and b <= sp[1]]
            if not act:
                continue
            props = {sp[2] for sp in act}
            if 'opacity' in props and props <= {'opacity', 'transform', 'translate'} \
                    and all(sp[3] for sp in act if sp[2] == 'opacity'):
                kind = 'appear'
            elif props == {'opacity'}:
                kind = 'fade'
            else:
                kind = 'action'
            out.append((a, b, kind))
        return out

    svg_idx = {i for i, e in enumerate(E) if e['tag'] == 'svg'}

    def local(tr, t):
        """Progress 0..1 inside the current iteration, or None when the track is not running."""
        x = t - tr['delay']
        if x < 0 or x >= tr['dur'] * tr['iters']:
            return None
        return (x % tr['dur']) / tr['dur']

    loopish = any(tr['iters'] == math.inf for ts in tracks.values() for tr in ts)
    horizon = cycle or 0.0
    for ts in tracks.values():
        for tr in ts:
            if tr['iters'] != math.inf:
                horizon = max(horizon, tr['delay'] + tr['dur'] * tr['iters'])
    horizon = horizon or 10.0
    # step stops at the last mark: anything that still changes after it never plays there
    if control == 'step' and phase_marks:
        last = 0.0
        for ts in tracks.values():
            for tr in ts:
                ends = [b for a, b, k in kf_moving(tr['name'])]
                if ends and tr['iters'] != math.inf:
                    last = max(last, tr['delay'] + tr['dur'] * (tr['iters'] - 1 + max(ends)))
        if last > phase_marks[-1] + 0.05:
            R.warn('control', f'step: the last mark is {phase_marks[-1]:g} s but the figure still changes until '
                   f'{round(last, 2):g} s; the presenter never sees that part and the slide does not reach the resting '
                   f'frame; end data-anim-phases on {round(last, 2):g} (or the pass, {horizon:g})', wrapper['line'])
    STEPS = [round(k * 0.02, 2) for k in range(int(horizon / 0.02) + 1)]
    mov_cache = {}
    moving_at = []
    # A staggered reveal is one thing: every element that is only appearing (opacity up from 0,
    # maybe with a settling transform) counts once together. Otherwise one "thing" per moving
    # element; opacity-only swaps inside one group (a status that cross-fades between stacked
    # copies in the same node) count once for that group.
    for t in STEPS:
        things, appearing = set(), False
        for i, ts in tracks.items():
            for tr in ts:
                p = local(tr, t)
                if p is None:
                    continue
                segs_ = mov_cache.setdefault(tr['name'], kf_moving(tr['name']))
                hit = [k for a, b, k in segs_ if a <= p < b]
                if not hit:
                    continue
                if all(k == 'appear' for k in hit):
                    appearing = True
                    continue
                par = E[i]['anc'][-1] if E[i]['anc'] else None
                things.add(('g', par) if all(k != 'action' for k in hit) and par is not None
                           and par not in svg_idx and E[par]['in_svg'] else ('e', i))
                break
        moving_at.append(len(things) + appearing)
    mx = max(moving_at or [0])
    tmx = STEPS[moving_at.index(mx)] if moving_at else 0
    mmsg = f'{mx} things move at once at t={tmx:g} s; at most three, or a staggered series'
    if mx > 6:
        R.fail('concurrency', mmsg)
    elif mx > 3:
        R.warn('concurrency', mmsg)
    else:
        R.ok('concurrency', f'motion: at most {mx} element(s) moving at once (t={tmx:g} s) over {horizon:g} s'
             + (' (loop)' if loopish else ''))
    R.ok('concurrency', f'info: {len({tr["name"] for ts in tracks.values() for tr in ts})} distinct animation '
         f'name(s) on {len(tracks)} element(s)')

    GLOW_RE = re.compile(r'\b(blur|drop-shadow)\(', re.I)
    glow_rules = []
    for sel, body, pos, ctx in walk_rules(tree):
        if ctx:
            continue
        if any(p == 'filter' and GLOW_RE.search(v) for p, v in decls(body)):
            for s1 in split_selectors(sel):
                glow_rules.append(parse_selector(strip_gate(s1))[0])
    glows = []
    for i, e in enumerate(E):
        if not e['in_svg'] or e['tag'] in NO_RENDER or any(E[a]['tag'] in NO_RENDER for a in e['anc']):
            continue
        fv = e['attrs'].get('filter', '') + ' ' + ' '.join(v for p, v in decls(e['attrs'].get('style', '')) if p == 'filter')
        if any('glow' in c for c in e['attrs'].get('class', '').split()) or GLOW_RE.search(fv) \
                or any(pr and selector_matches(pr, i, E) for pr in glow_rules):
            glows.append(i)

    def opacity_at(i, t):
        base = css_number(resolved(i, 'opacity') or '1')
        val = 1.0 if base is None else base
        for tr in tracks.get(i, []):
            st = [(pct / 100, css_number(d['opacity'])) for pct, d in keyframes.get(tr['name'], []) if 'opacity' in d]
            st = [(p, v) for p, v in st if v is not None]
            if not st:
                continue
            x = t - tr['delay']
            end = tr['dur'] * tr['iters']
            if x < 0:
                if tr['fill'] in ('backwards', 'both'):
                    val = st[0][1]
                continue
            if x >= end:
                if tr['fill'] in ('forwards', 'both'):
                    val = st[-1][1]
                continue
            p = (x % tr['dur']) / tr['dur']
            if st[0][0] > 0:
                st.insert(0, (0.0, val))
            if st[-1][0] < 1:
                st.append((1.0, val))
            for (p0, v0), (p1, v1) in zip(st, st[1:]):
                if p0 <= p <= p1:
                    val = v0 if p1 == p0 else v0 + (v1 - v0) * (p - p0) / (p1 - p0)
                    break
        return val

    def visible(i, t):
        return all(opacity_at(j, t) > 0.01 for j in [i] + list(E[i]['anc']))

    gsteps = STEPS + [round(horizon + 1, 2)]     # one sample after the pass: fill forwards
    gl_at = [sum(1 for i in glows if visible(i, t)) for t in gsteps]
    gx = max(gl_at or [0])
    tg = gsteps[gl_at.index(gx)] if gl_at else 0
    gmsg = f'{gx} glows visible at once at t={tg:g} s; one glowing element at most'
    if gx > 2:
        R.fail('concurrency', gmsg, E[glows[0]]['line'] if glows else None)
    elif gx > 1:
        R.warn('concurrency', gmsg, E[glows[0]]['line'] if glows else None)
    else:
        R.ok('concurrency', f'glow: at most {gx} glow element(s) visible at once ({len(glows)} in total)')
    for i in glows:
        e = E[i]
        if e['tag'] in ('line', 'polyline') or (e['tag'] == 'path' and (resolved(i, 'fill') or '').lower() == 'none'):
            R.warn('concurrency', f'{describe(e)} glows but is stroke-only: lines and arrows never glow', e['line'])

    # ------------------------------------------------------------------ index-class collisions
    # Per-index classes (<name>-mk0, -mk1, ...) are usually generated in a loop. A hand-written
    # class that happens to read <name>-mk0 picks up index 0's rules. Signature: the elements
    # with that one index lack the classes every other index of the series shares.
    nf0 = len(R.items)
    series = {}   # stem -> {index: [element]}
    for e in E:
        for c in e['attrs'].get('class', '').split():
            m = re.fullmatch(re.escape(pref) + r'(.*?[A-Za-z_-])(\d+)', c)
            if m:
                series.setdefault(m.group(1), {}).setdefault(int(m.group(2)), []).append(e)
    # an index is "generated" when some selector shape is written for it and two other indices
    templates = {}   # (stem, selector with the index blanked) -> {index}
    for sel, body, pos, ctx in walk_rules(tree):
        for s in split_selectors(sel):
            for m in re.finditer(r'\.' + re.escape(pref) + r'([\w-]*?[A-Za-z_-])(\d+)(?![\w-])', s):
                t = s[:m.start()] + '.' + pref + m.group(1) + '#' + s[m.end():]
                templates.setdefault((m.group(1), t), set()).add(int(m.group(2)))
    for stem, idxs in sorted(series.items()):
        if len(idxs) < 4:
            continue
        stem_cls = {f'{pref}{stem}{k}' for k in idxs}
        generated = set().union(*([v for (st, t), v in templates.items() if st == stem and len(v) >= 3] or [set()]))
        for k, els in sorted(idxs.items()):
            if k not in generated:
                continue
            others = [x for j, xs in idxs.items() if j != k for x in xs]
            core = set.intersection(*[set(x['attrs'].get('class', '').split()) for x in others]) - stem_cls
            if not core:
                continue
            odd = [x for x in els if not core <= set(x['attrs'].get('class', '').split())]
            if len(odd) >= 2 and len(odd) * 2 >= len(els):
                R.warn('index-collision', f'class "{pref}{stem}{k}" is on {len(odd)} element(s) without '
                       f'{", ".join(sorted(core))}, which every other {pref}{stem}<i> element has: a '
                       f'hand-written class may collide with the per-index series; rename it '
                       f'(e.g. {pref}{stem}-o)', odd[0]['line'])
    if len(R.items) == nf0:
        R.ok('index-collision', f'{len(series)} per-index class series, no collisions')

    sys.exit(1 if R.print() else 0)


if __name__ == '__main__':
    main()
