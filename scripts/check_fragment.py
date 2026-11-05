#!/usr/bin/env python3
"""Static contract checks for an anim-slides fragment (references/fragment-contract.md).

Usage:
  check_fragment.py FRAGMENT.html --name NAME --rendered-width PX
                    [--min-text 18] [--gate .visible|none] [--control loop|step]

  --rendered-width  width in CSS px at which the SVG is shown on the stage
  --min-text        minimum rendered text size in px (18 on a 1920 stage, scale for others)
  --gate            ancestor selector that gates the animations (default .visible)
  --control         loop | step (default: the wrapper's data-anim-control, else loop)

Every finding is printed as OK / WARN / FAIL with a line hint. Exit code 1 on any FAIL.
Standard library only.
"""
import argparse
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
        el = dict(tag=tag, attrs=a, line=line, anc=list(self.stack), in_svg=self.svg_depth > 0)
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


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('fragment')
    ap.add_argument('--name', required=True)
    ap.add_argument('--rendered-width', type=float, required=True)
    ap.add_argument('--min-text', type=float, default=18)
    ap.add_argument('--gate', default='.visible', help='gate selector, or "none"')
    ap.add_argument('--control', choices=['loop', 'step'], default=None)
    a = ap.parse_args()

    src = open(a.fragment, encoding='utf-8').read()
    name, pref = a.name, a.name + '-'
    wrap_cls = f'anim-{name}'
    gate = None if a.gate.strip().lower() == 'none' else a.gate.strip()
    gate_classes = set(re.findall(r'\.([\w-]+)', gate)) if gate else set()
    R = Report()

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
    if wrapper:
        wa = wrapper['attrs']
        if wa.get('data-anim') != name:
            R.fail('structure', f'wrapper needs data-anim="{name}"', wrapper['line'])
        cyc = wa.get('data-anim-cycle')
        if cyc is None:
            R.fail('structure', 'wrapper needs data-anim-cycle="<seconds>"', wrapper['line'])
        elif not re.fullmatch(r'\d+(\.\d+)?', cyc.strip()):
            R.fail('structure', f'data-anim-cycle="{cyc}" is not numeric', wrapper['line'])
        ctl = wa.get('data-anim-control', 'loop')
        if ctl not in ('loop', 'step'):
            R.fail('structure', f'data-anim-control="{ctl}" must be loop or step', wrapper['line'])
        elif ctl == 'loop' and cyc and re.fullmatch(r'\d+(\.\d+)?', cyc.strip()) \
                and not 8 <= float(cyc) <= 15:
            R.fail('structure', f'data-anim-cycle="{cyc}" outside 8 to 15 s (contract section 6)', wrapper['line'])
        control = control or ctl
    control = control or 'loop'

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
        R.ok('structure', f'one <style>, wrapper div.anim.{wrap_cls}, one <svg> (viewBox width {vbw:g}), control={control}')

    # ------------------------------------------------------------------ forbidden
    nf0 = len(R.items)
    scripts = mk.scripts
    if control == 'step':
        mods = [s for s in scripts if s['attrs'].get('type') == 'module']
        if len(scripts) != 1 or len(mods) != 1:
            R.fail('forbidden', f'step control needs exactly one <script type="module">, found {len(scripts)} script(s)')
        for s in scripts:
            if 'src' in s['attrs']:
                R.fail('forbidden', '<script src> not allowed; inline the module', s['line'])
            if not s['after_svg']:
                R.fail('forbidden', 'the module script must come after the </svg>', s['line'])
            if f"register('{name}'" not in s['body'] and f'register("{name}"' not in s['body']:
                R.warn('forbidden', f'script does not call window.animSlides.register("{name}", tl)', s['line'])
    else:
        for s in scripts:
            R.fail('forbidden', '<script> not allowed with control=loop', s['line'])
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
        R.ok('forbidden', 'no external resources' + (', one module script' if control == 'step' else ', no script'))

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
            (R.ok if control == 'step' else R.warn)('gating', 'no CSS animations found'
                                                   + (' (step control: GSAP drives motion)' if control == 'step' else ''))
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
                R.fail('text-size', f'{where} {px:g}px renders at {px * scale:.1f}px < {a.min_text:g}px', ln)

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
            R.warn('text-size', f'largest text renders at {max(sizes):.1f}px < {title_min:g}px: fine without a '
                   'title, otherwise titles must reach the title floor (contract section 6)')
        if len(R.items) == nf0:
            R.ok('text-size', f'{len(sizes)} sizes, smallest {min(sizes):.1f}px at {a.rendered_width:g}px wide'
                 f' (min {a.min_text:g})' if sizes else 'no explicit font sizes')

    # ------------------------------------------------------------------ resting frame heuristic
    nf0 = len(R.items)
    ends_hidden = set()

    def kf_ends_hidden(nodes):
        for nd in nodes:
            if nd[0] == 'keyframes':
                for k in nd[2]:
                    if k[0] == 'rule' and {x.strip() for x in k[1].split(',')} & {'to', '100%'}:
                        if any(p == 'opacity' and re.fullmatch(r'0*\.?0*', v.strip()) for p, v in decls(k[2])):
                            ends_hidden.add(nd[1])
            elif nd[0] == 'at':
                kf_ends_hidden(nd[2])
    kf_ends_hidden(tree)

    base_opacity = []   # class sets of ungated rules that set opacity
    for sel, body, pos, ctx in walk_rules(tree):
        if ctx:
            continue
        if any(p == 'opacity' for p, _ in decls(body)):
            for s in split_selectors(sel):
                if not (gate_re and re.match(gate_re, s)):
                    base_opacity.append(last_compound_classes(s))
    flagged = {}   # keyframes names -> [(element, line)]
    for s, v, ln, g, ctx in anim_rules:
        if ctx:
            continue
        names = set(re.findall(r'(?<![\w-])([A-Za-z_][\w-]*)', v)) & ends_hidden
        if not names:
            continue
        finite = not re.search(r'\binfinite\b', v) or re.search(r'\b(forwards|both)\b', v)
        want = last_compound_classes(s)
        for e in E:
            ec = set(e['attrs'].get('class', '').split())
            if not want or not want <= ec:
                continue
            has = ('opacity' in e['attrs'] or 'opacity' in e['attrs'].get('style', '')
                   or any(bo and bo <= ec for bo in base_opacity))
            if not has:
                key = (', '.join(sorted(names)), bool(finite))
                flagged.setdefault(key, []).append(e)
    for (names, finite), els in sorted(flagged.items()):
        first = els[0]
        what = ' '.join(sorted(first['attrs'].get('class', '').split()))
        R.warn('resting-frame', f'keyframes {names} end at opacity 0 and <{first["tag"]} class="{what}">'
               + (f' (+{len(els) - 1} more)' if len(els) > 1 else '')
               + ' has no base opacity rule'
               + (': a finite/forwards animation leaves it invisible' if finite else
                  ': fine if it should rest visible, otherwise set the end state in the base rule'),
               first['line'])
    if len(R.items) == nf0:
        R.ok('resting-frame', 'no element ends a cycle invisible without a base opacity')

    sys.exit(1 if R.print() else 0)


if __name__ == '__main__':
    main()
