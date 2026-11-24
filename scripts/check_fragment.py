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
as one: WARN > 3, FAIL > 6; an element counts as part of the reveal while it shows for the first
time: opacity up from 0, a draw-on to stroke-dashoffset 0, a clip reveal from fully clipped, a
scale from 0.9 or more settling with a fade-in) and
glow concurrency (glow elements visible at the same instant: WARN > 1, FAIL > 2; a stroke-only
glow warns: lines and arrows never glow).
Staggered series: data-anim-series="<id>" on an element or on a parent <g> declares a series of
like units (sort, accumulate: one element per unit). Its members moving at one instant count as
ONE move only if the series is one: at most 100 animated members (more: FAIL), all animating the
same set of properties, consecutive start times at most 120 ms apart and each burst of motion (a
staged step: members whose moves overlap) over within 1.6 s. Otherwise a WARN names the series
and the rule it breaks, and its members count separately. Stacked copies running the same d
(path) keyframes with the same timing count as one shape.
Variants: rules inside a positive @supports block (e.g. @supports (d: path("M0 0")) for a path
morph) form a second variant (base rules plus that block); resting frame, control and
concurrency are checked for the base and for each variant, the animation each element runs is
decided by the cascade, display: none elements do not count as moving, and a d track's 100 %
keyframe must equal the resting d (the resting rule's d, else the d attribute): FAIL. Findings
of a variant are prefixed with its condition. @media blocks are left out, as before.
Verb: data-anim-verb on the wrapper names the main motion (references/motion-verbs.md): missing
WARN, not one of the twenty verbs or reveal FAIL; WARN on offset-path motion under a verb other
than travel or cycle, and on travel without any offset-path.
Look (findings carry their id in brackets, references/motion-rules.md and style.md):
  [easing-set]      WARN: a timing function outside the set enter cubic-bezier(0.16,1,0.3,1),
                    move (0.2,0,0,1), exit (0.3,0,1,1), land (0.3,1.3,0.5,1), linear, steps(),
                    step-start/end (compared to 0.005); once per value with a count and the nearest
  [overshoot]       FAIL: a cubic-bezier with y1 or y2 outside 0 to 1 that is not land; an animation
                    or keyframes name with bounce, elastic, wobble or jiggle
  [fade-after-fade] WARN: at least 5 animated non-text elements and 80 % of them only fade
                    (opacity, at most a 24 px translate)
  [mono-costume]    WARN: var(--anim-mono) text with no digit, no code-like token, not a unit and not a math symbol
  [type-ladder]     WARN: two text sizes less than 1.2x apart (sizes within 2 % are one), or more
                    than four sizes
  [focal]           WARN without data-anim-focal; FAIL when more than one element carries it
  [node-count]      WARN over 12 nodes; nodes are known only by the scaffolder's class NAME-node
  [stillness]       WARN unless 380 ms or more with nothing moving (fades and caption cross-fades
                    count as motion; same per-element motion data as concurrency) precede the final
                    burst before the last phase mark. The final burst: the last motion before the
                    last mark plus the pieces before it that follow within 0.3 s of each other,
                    never reaching back to a piece that starts more than 0.3 s before the
                    second-last mark (the answer step is the last phase). INFO (exempt): control
                    loop, fewer than two phase marks, or main verb trace with one linear move
                    running more than half the pass. Easing tails count as motion: a draw-on whose
                    last few percent are sub-pixel still blocks the window

Every finding is printed as OK / WARN / FAIL (INFO for notes) with a line hint. Exit code 1 on any FAIL.
Standard library only.
"""
import argparse
import math
import re
import sys
import unicodedata
from html.parser import HTMLParser

# references/motion-verbs.md: twenty verbs plus reveal; keep in step with scaffold_from_spec.py VERBS
VERBS = ('grow', 'count', 'accumulate', 'thin', 'race', 'split', 'merge', 'sort', 'stack', 'nest',
         'transform', 'wipe', 'switch', 'balance', 'drive', 'zoom', 'open', 'travel', 'trace', 'cycle',
         'reveal')

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


def path_key(v):
    """A path, from a d attribute or a CSS d: path("...") value, as comparable tokens."""
    v = (v or '').replace('!important', '').strip()
    m = re.fullmatch(r'path\(\s*["\']?(.*?)["\']?\s*\)', v, re.S)
    v = m.group(1) if m else v
    out = []
    for tok in re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?', v):
        out.append(tok if tok.isalpha() else round(float(tok), 2))
    return tuple(out)


# ----------------------------------------------------------------------------- easing set
# The only curves allowed (references/motion-rules.md, one easing set). land overshoots on purpose.
EASINGS = {'enter': (0.16, 1.0, 0.3, 1.0), 'move': (0.2, 0.0, 0.0, 1.0),
           'exit': (0.3, 0.0, 1.0, 1.0), 'land': (0.3, 1.3, 0.5, 1.0)}
EASE_USE = {'enter': 'things arriving, draw-on, reveals', 'move': 'things on screen changing place or size',
            'exit': 'things leaving', 'land': 'a small mark arriving'}
EASE_KEYWORDS = {'ease': (0.25, 0.1, 0.25, 1.0), 'ease-in': (0.42, 0.0, 1.0, 1.0),
                 'ease-out': (0.0, 0.0, 0.58, 1.0), 'ease-in-out': (0.42, 0.0, 0.58, 1.0)}
EASE_TOL = 0.005
TIMING_RE = re.compile(r'(?<![\w-])(cubic-bezier|steps|linear)\s*\(([^)]*)\)'
                       r'|(?<![\w-])(ease-in-out|ease-in|ease-out|ease|linear|step-start|step-end)(?![\w-])', re.I)
TIMING_PROPS = re.compile(r'(?<![\w-])(animation|animation-timing-function|transition|transition-timing-function)'
                          r'\s*:\s*([^;{}]*)', re.I)
BAD_NAME_RE = re.compile(r'bounce|elastic|wobble|jiggle', re.I)
# a clip that hides everything: an inset of 100 % on a side, or a circle/ellipse of radius 0
CLIPPED_RE = re.compile(r'inset\([^)]*\b(?:100(?:\.0+)?|99(?:\.\d+)?)%|(?:circle|ellipse)\(\s*0(?:px|%)?(?:\s|\)|,)', re.I)


def bezier_y(p, x):
    """y of the CSS cubic-bezier p = (x1, y1, x2, y2) at progress x (bisection on t)."""
    x1, y1, x2, y2 = p

    def b(t, a1, a2):
        return 3 * (1 - t) ** 2 * t * a1 + 3 * (1 - t) * t * t * a2 + t ** 3
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if b(mid, x1, x2) < x:
            lo = mid
        else:
            hi = mid
    return b((lo + hi) / 2, y1, y2)


def nearest_easing(p, allow_land=False):
    """Name of the curve of the set that is closest to p over the whole progress range. A curve
    that slows down into its end (an ease-out or an ease-in-out) is never matched with exit,
    which speeds up into its end; one that speeds up into its end always is."""
    xs = [k / 20 for k in range(1, 20)]
    ys = [bezier_y(p, x) for x in xs]
    settles = p[3] >= 0.99 and p[2] <= 0.9
    if not settles:
        return 'exit'
    best = None
    for nm, q in EASINGS.items():
        if (nm == 'land' and not allow_land) or nm == 'exit':
            continue
        d = sum(abs(y - bezier_y(q, x)) for x, y in zip(xs, ys))
        if best is None or d < best[0]:
            best = (d, nm)
    return best[1]


def ease_str(nm):
    q = EASINGS[nm]
    return f'{nm} cubic-bezier({", ".join(f"{v:g}" for v in q)})'


def parse_timing(m):
    """(key, label, bezier or None, kind) for one TIMING_RE match. kind: ok | bad | overshoot."""
    fn, args, kw = m.group(1), m.group(2), m.group(3)
    if fn:
        fn = fn.lower()
        if fn == 'steps':
            return ('steps', 'steps()', None, 'ok')
        if fn == 'linear':   # linear(<points>) can draw any curve, also a bounce
            return ('linear()', f'linear({" ".join(args.split())})', None, 'bad')
        try:
            p = tuple(float(v) for v in args.replace(',', ' ').split())
        except ValueError:
            p = ()
        if len(p) != 4:
            return ('cb?' + args, f'cubic-bezier({args})', None, 'bad')
        label = f'cubic-bezier({", ".join(f"{v:g}" for v in p)})'
        for q in EASINGS.values():
            if all(abs(a - b) <= EASE_TOL for a, b in zip(p, q)):
                return (q, label, p, 'ok')
        if not (0 <= p[1] <= 1 and 0 <= p[3] <= 1):
            return (tuple(round(v, 3) for v in p), label, p, 'overshoot')
        return (tuple(round(v, 3) for v in p), label, p, 'bad')
    kw = kw.lower()
    if kw in ('linear', 'step-start', 'step-end'):
        return (kw, kw, None, 'ok')
    return (kw, kw, EASE_KEYWORDS[kw], 'bad')


class VariantReport:
    """Reporter for one CSS variant: the base variant reports as usual; an @supports variant
    adds only problems the base did not already report, prefixed with its condition."""

    def __init__(self, base, label):
        self.base, self.label, self.items = base, label, base.items

    def add(self, level, check, msg, line=None):
        if self.label is None:
            return self.base.add(level, check, msg, line)
        if level not in ('WARN', 'FAIL'):
            return None
        text = msg + (f' (line {line})' if line else '')
        if (level, check, text) not in self.items:
            self.base.add(level, check, f'[{self.label}] {msg}', line)

    def ok(self, check, msg):
        self.add('OK', check, msg)

    def warn(self, check, msg, line=None):
        self.add('WARN', check, msg, line)

    def fail(self, check, msg, line=None):
        self.add('FAIL', check, msg, line)


SERIES_MAX, SERIES_GAP, SERIES_SPAN = 100, 0.12, 1.6


def check_series(tracks, kf_moving, moving_props, R, E):
    """data-anim-series="<id>" on an element or a parent <g> declares a staggered series of
    like units (sort, accumulate). Members moving at one instant count as ONE move only when the
    series is one: at most 100 animated members, all animating the same set of properties,
    consecutive start times at most 120 ms apart and each burst of motion (a staged step) over
    within 1.6 s. Returns (ids that count as one move, {element: (series id, carrier index)})."""
    carrier = {}
    for i, e in enumerate(E):
        for j in [i] + list(reversed(e['anc'])):
            if 'data-anim-series' in E[j]['attrs']:
                carrier[i] = (E[j]['attrs']['data-anim-series'].strip(), j)
                break
    members = {}
    for i in tracks:
        if i in carrier:
            members.setdefault(carrier[i][0], []).append(i)
    ok = set()
    for sid, mem in sorted(members.items()):
        line = E[carrier[mem[0]][1]]['line']
        if len(mem) > SERIES_MAX:
            R.fail('concurrency', f'data-anim-series="{sid}" has {len(mem)} animated members; at most '
                   f'{SERIES_MAX} (one unit = a larger amount); its members count separately', line)
            continue
        props, ivs = {}, []
        for i in mem:
            pr, own = set(), []
            for tr in tracks[i]:
                for a, b, kind in kf_moving(tr['name']):
                    own.append((tr['delay'] + a * tr['dur'], tr['delay'] + b * tr['dur']))
                for k in moving_props(tr['name']):
                    pr.add(k)
            props[i] = frozenset(pr)
            own.sort()
            for a, b in own:      # one continuous move per member, however many keyframe segments
                if ivs and ivs[-1][2] == i and a <= ivs[-1][1] + 0.02:
                    ivs[-1] = (ivs[-1][0], max(ivs[-1][1], b), i)
                else:
                    ivs.append((a, b, i))
        why = None
        if len(set(props.values())) > 1:
            kinds = sorted({', '.join(sorted(v)) or 'nothing' for v in props.values()})
            why = 'members animate different properties (' + ' / '.join(kinds[:3]) + ')'
        ivs.sort()
        k = 0
        while why is None and k < len(ivs):
            j, end = k, ivs[k][1]
            while j + 1 < len(ivs) and ivs[j + 1][0] <= end + 0.02:
                j += 1
                end = max(end, ivs[j][1])
            starts = [x[0] for x in ivs[k:j + 1]]
            gaps = [(b - a, a) for a, b in zip(starts, starts[1:])]
            big = max(gaps, default=(0, 0))
            if big[0] > SERIES_GAP + 0.005:
                why = (f'consecutive members start {big[0] * 1000:.0f} ms apart at t={big[1]:.2f} s '
                       f'(at most {SERIES_GAP * 1000:.0f} ms)')
            elif end - starts[0] > SERIES_SPAN + 0.02:
                why = (f'the series is in motion for {end - starts[0]:.2f} s from t={starts[0]:.2f} s '
                       f'(at most {SERIES_SPAN:g} s per staged step)')
            k = j + 1
        if why:
            R.warn('concurrency', f'data-anim-series="{sid}" ({len(mem)} members) is not one staggered move: '
                   f'{why}; its members count separately', line)
        else:
            ok.add(sid)
            R.ok('concurrency', f'data-anim-series="{sid}": {len(mem)} members, one staggered move')
    return ok, carrier


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

    # ------------------------------------------------------------------ verb (references/motion-verbs.md)
    if wrapper:
        verb = wrapper['attrs'].get('data-anim-verb')
        uses_offset = bool(re.search(r'(?<![\w-])offset-path\s*:', css)) or any(
            re.search(r'(?<![\w-])offset-path\s*:', e['attrs'].get('style', '')) for e in E)
        if verb is None:
            R.warn('verb', 'wrapper has no data-anim-verb="<verb>": name the main motion from '
                   'references/motion-verbs.md (travel only when a named thing changes place)', wrapper['line'])
        elif not verb.split() or len(verb.split()) > 3 or any(v not in VERBS for v in verb.split()):
            R.fail('verb', f'data-anim-verb="{verb}": the main verb, then at most two supporting verbs, each one of '
                   f'{", ".join(VERBS)}', wrapper['line'])
        else:
            n0 = len(R.items)
            verbs_named = verb.split()
            if uses_offset and not ({'travel', 'cycle'} & set(verbs_named)):
                R.warn('verb', f'offset-path motion (a travelling marker) under data-anim-verb="{verb}": a '
                       'marker on a path is travel; draw the verb\'s own change, or name travel (as the '
                       'main verb, or after it as a supporting verb) and name the traveller', wrapper['line'])
            if len(R.items) == n0:
                R.ok('verb', f'data-anim-verb="{verb}"' + (' with offset-path motion' if uses_offset else ''))

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

    # ------------------------------------------------------------------ easing set and overshoot
    # Every timing function (animation, transition, keyframe stops, inline styles) is one of the
    # set: enter, move, exit, land, linear, steps(). Other curves warn; overshooting ones fail.
    found = {}   # key -> [label, bezier, kind, count, first line]
    srcs = [(css, style_pos)] + [(e['attrs']['style'], None, e['line']) for e in E if 'style' in e['attrs']]
    for item in srcs:
        text, base = item[0], item[1]
        for dm in TIMING_PROPS.finditer(text):
            for m in TIMING_RE.finditer(dm.group(2)):
                key, label, p, kind = parse_timing(m)
                ln = line_of(base + dm.start()) if base is not None else item[2]
                f = found.setdefault(key, [label, p, kind, 0, ln])
                f[3] += 1
    n_ok = sum(f[3] for f in found.values() if f[2] == 'ok')
    bad = [f for f in found.values() if f[2] == 'bad']
    over = [f for f in found.values() if f[2] == 'overshoot']
    for label, p, kind, n, ln in sorted(bad, key=lambda f: -f[3]):
        alt = nearest_easing(p) if p else 'enter'
        R.warn('[easing-set]', f'{label} used {n}x: not in the easing set; use {ease_str(alt)} '
               f'({EASE_USE[alt]}), or another curve of the set: enter, move, exit, land (small marks '
               'only), linear (continuous motion), steps() (digit strips)', ln)
    for label, p, kind, n, ln in over:
        R.fail('[overshoot]', f'{label} used {n}x overshoots (y1 or y2 outside 0 to 1) and is not the land '
               f'curve: no bounce; use {ease_str(nearest_easing(p))}, or land cubic-bezier(0.3, 1.3, 0.5, 1) '
               'for a small mark arriving (at most 48 px)', ln)
    bad_names = set()
    for nd_name, ln in [(nd[1], line_of(style_pos + nd[3])) for nd in tree if nd[0] == 'keyframes']:
        if BAD_NAME_RE.search(nd_name):
            bad_names.add((nd_name, ln))
    for s, v, ln, g, ctx in anim_rules:
        for w in re.findall(r'(?<![\w-])([A-Za-z_][\w-]*)', re.sub(r'\([^)]*\)', '', v)):
            if BAD_NAME_RE.search(w):
                bad_names.add((w, ln))
    for nm, ln in sorted(bad_names)[:3]:
        R.fail('[overshoot]', f'animation "{nm}" names a bounce, elastic, wobble or jiggle: motion settles once '
               'without overshoot; use the enter or move curve (land only for a small mark)', ln)
    if not bad and not over and not bad_names:
        R.ok('[easing-set]', f'{n_ok} timing function(s), all from the easing set')

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

    # ------------------------------------------------------------------ variants (@supports)
    # The base variant is every rule outside at-rules (plus @supports not (...) blocks: what a
    # browser without the feature runs). Each positive @supports block, e.g. the d: path() morph
    # recommended in motion-verbs.md, is a second variant: the base rules plus that block, the
    # Chromium/Firefox picture. Resting frame, control and concurrency run once per variant;
    # findings of a non-base variant are prefixed with it and reported only when they differ.
    # @media blocks (prefers-reduced-motion) are left out of both, as before.
    sup = []

    def find_sup(nodes):
        for nd in nodes:
            if nd[0] == 'at':
                pre = ' '.join(nd[1].split())
                if pre.lower().startswith('@supports') and not re.match(r'@supports\s+not\b', pre, re.I) \
                        and pre not in sup:
                    sup.append(pre)
    find_sup(tree)
    R_main = R
    for variant in [None] + sup:
        R = VariantReport(R_main, variant)

        def acc(ctx, variant=variant):
            ctx = tuple(' '.join(c.split()) for c in ctx)
            if variant is None:
                return all(re.match(r'@supports\s+not\b', c, re.I) for c in ctx)
            return ctx == () or ctx == (variant,)
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

        def collect_kf(nodes, ctx=()):
            for nd in nodes:
                if nd[0] == 'keyframes' and acc(ctx):
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
                    collect_kf(nd[2], ctx + (nd[1],))
        collect_kf(tree)

        def strip_gate(s):
            return re.sub('^' + gate_re, '', s) if gate_re and re.match(gate_re, s) else s

        # base (ungated, outside @media) declarations of the three hiding properties
        HIDE_PROPS = ('opacity', 'visibility', 'display', 'fill', 'd')   # d: the resting path of a morph   # fill: for the glow-on-a-line check
        base_rules = []   # (parsed, spec, order, {prop: (value, important)})
        order = 0
        for sel, body, pos, ctx in walk_rules(tree):
            order += 1
            dd = {p: (v.replace('!important', '').strip(), '!important' in v)
                  for p, v in decls(body) if p in HIDE_PROPS}
            if not acc(ctx) or not dd:
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
            if not acc(ctx) or not vals:
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
            if not acc(ctx) or re.search(r'\binfinite\b', v) or not re.search(r'\b(forwards|both)\b', v):
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
                if not acc(ctx) or (gate and not g):
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
            ends, dends = [], []
            for i, tracks in anims.items():
                if i in unsure:
                    continue
                for names, d in tracks:
                    for nm in names:
                        dpts = [(pct, dd['d']) for pct, dd in keyframes.get(nm, []) if 'd' in dd]
                        if dpts and dpts[-1][0] >= 100.0:
                            rest_d = resolved(i, 'd')
                            if rest_d is not None and path_key(dpts[-1][1]) != path_key(rest_d):
                                dends.append((E[i], nm, dpts[-1][1], rest_d))
                        pts = [(pct, dd['opacity']) for pct, dd in keyframes.get(nm, []) if 'opacity' in dd]
                        if not pts or pts[-1][0] < 100.0:
                            continue    # no 100 % stop: the browser ends on the base value, i.e. the resting frame
                        end = css_number(pts[-1][1])
                        rest = resolved(i, 'opacity')
                        restn = 1.0 if rest is None else css_number(rest)
                        if end is not None and restn is not None and abs(end - restn) > 0.01:
                            ends.append((E[i], nm, end, restn))
            for e, nm, end, rest_d in dends[:5]:
                R.fail('control', f'{describe(e)}: keyframes {nm} end at d {end[:50]} but the resting d is '
                       f'{rest_d[:50]}; the 100 % keyframe must equal the resting frame (set the same path in '
                       'the resting rule, or as the d attribute)', e['line'])
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
            tf = lg('animation-timing-function')
            linear = bool(re.search(r'(?<![\w-])linear(?![\w-])', bare)) or (tf or '').strip() == 'linear'
            return {'name': sorted(nm)[0], 'dur': dur, 'delay': max(0.0, delay or 0.0), 'iters': iters, 'fill': fill,
                    'linear': linear}

        tracks = {}      # element index -> [track]
        # the cascade decides which animation an element runs: the matching animation
        # declaration with the highest (!important, specificity, source order) wins, so a rule in
        # an @supports block that replaces a base animation replaces it (no union of tracks)
        win, order_n = {}, 0
        for sel, body, pos, ctx in walk_rules(tree):
            if not acc(ctx):
                continue
            dd = decls(body)
            longs = {p: v for p, v in dd if p.startswith('animation-')}
            for p, v in dd:
                if p not in ('animation', 'animation-name'):
                    continue
                order_n += 1
                imp = '!important' in v
                v = v.replace('!important', '').strip()
                if v.lower() == 'none':
                    parsed_tr = []
                else:
                    parsed_tr = [t for t in (parse_anim(x, longs, k) for k, x in enumerate(split_top(v))) if t]
                    if not parsed_tr:
                        continue
                for s1 in split_selectors(sel):
                    parsed, _ = parse_selector(strip_gate(s1))
                    if parsed is None:
                        continue
                    key = (int(imp), parse_selector(s1)[1], order_n)
                    for i in range(len(E)):
                        if selector_matches(parsed, i, E) and (i not in win or key > win[i][0]):
                            win[i] = (key, parsed_tr)
        for i, (key, trs) in win.items():
            # an element that this variant hides with display: none does not move on screen
            if trs and not any((resolved(j, 'display') or '').lower() == 'none' for j in [i] + list(E[i]['anc'])):
                tracks[i] = list(trs)

        def same_value(v):
            """A keyframe value in one spelling: 0.96 and .96, 1 and 1.0, spacing, compare equal."""
            return re.sub(r'(?<![\w#])(-?\d*\.?\d+)', lambda m: repr(float(m.group(1))), ' '.join(v.split()))

        def kf_moving(name):
            """[(p0, p1, kind)] in 0..1 where keyframes `name` change something. Each property is
            followed on its own (CSS interpolates a property between the stops that name it, so a
            stop that omits it changes nothing). kind: 'appear' = the element shows for the first
            time and nothing else changes: opacity rises from 0 (optionally with a transform or a
            scale from 0.9 or more settling), a draw-on (stroke-dashoffset from its first value to
            0), or a clip reveal (clip-path from fully clipped); 'fade' = another opacity-only
            change; 'action' = anything else."""
            per = {}
            for pct, d in keyframes.get(name, []):
                for k, v in d.items():
                    if k != 'animation-timing-function':
                        per.setdefault(k, []).append((pct / 100, v))
            segs_p = []    # (p0, p1, prop, appearing: first shown or drawn by this segment)
            for k, pts in per.items():
                first = True    # no earlier change of this property: the element was not shown yet
                for (a, va), (b, vb) in zip(pts, pts[1:]):
                    if b > a and same_value(va) != same_value(vb):
                        n0, n1 = css_number(va), css_number(vb)
                        if k == 'opacity':
                            app = n0 is not None and n1 is not None and n0 <= 0.01 and n1 > n0
                        elif k == 'stroke-dashoffset':    # draw-on: from undrawn to fully drawn
                            app = first and n0 is not None and n1 is not None and abs(n1) < 0.01 < abs(n0)
                        elif k in ('clip-path', '-webkit-clip-path'):    # clip reveal from fully clipped
                            app = first and bool(CLIPPED_RE.search(va)) and not CLIPPED_RE.search(vb)
                        elif k == 'scale':
                            s0 = css_number(va.split()[0]) if va.split() else None
                            app = s0 is not None and 0.9 <= s0 < 1 and css_number(vb.split()[0]) == 1
                        else:
                            app = False
                        segs_p.append((a, b, k, app))
                        first = False
            cuts = sorted({x for a, b, _, _ in segs_p for x in (a, b)})
            out = []
            for a, b in zip(cuts, cuts[1:]):
                act = [sp for sp in segs_p if sp[0] <= a and b <= sp[1]]
                if not act:
                    continue
                props = {sp[2] for sp in act}
                # appearing: every changing property shows the element for the first time (opacity
                # up from 0, a draw-on, a clip reveal), and a transform settles only with a fade-in
                reveal = [sp for sp in act if sp[2] not in ('transform', 'translate', 'scale')]
                fade_in = any(sp[3] for sp in act if sp[2] == 'opacity')
                if reveal and all(sp[3] for sp in reveal) \
                        and (fade_in or props <= {'stroke-dashoffset', 'clip-path', '-webkit-clip-path'}) \
                        and all(sp[3] for sp in act if sp[2] == 'scale'):
                    kind = 'appear'
                elif props == {'opacity'}:
                    kind = 'fade'
                else:
                    kind = 'action'
                out.append((a, b, kind))
            return out

        def moving_props(name):
            per = {}
            for pct, d in keyframes.get(name, []):
                for k, v in d.items():
                    if k != 'animation-timing-function':
                        per.setdefault(k, set()).add(v.strip())
            return {k for k, vs in per.items() if len(vs) > 1}

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
        one_move, carrier = check_series(tracks, kf_moving, moving_props, R, E)
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
                    if i in carrier and carrier[i][0] in one_move:
                        things.add(('s', carrier[i][0]))
                        break
                    if 'd' in moving_props(tr['name']):
                        # stacked copies of one shape (a stroke under a stroke) run the same path keyframes
                        # with the same timing: one shape on screen, one move
                        things.add(('k', tr['name'], tr['delay'], tr['dur']))
                        break
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

        # ------------------------------------------------------------------ stillness before the answer
        # motion-rules.md: one deliberate pause of 400 to 600 ms where nothing moves, just before the
        # answer step (the last staged step). The same motion data as above: every track's changing
        # keyframe segments (appearing, fades and caption cross-fades included) laid out in time.
        if variant is None:
            vb_ = (wrapper['attrs'].get('data-anim-verb') or '').split() if wrapper else []
            mov_iv = []          # (start, end) in s while something moves
            trace_run = 0.0      # longest continuous linear run of one track
            for i, ts in tracks.items():
                for tr in ts:
                    segs_ = mov_cache.setdefault(tr['name'], kf_moving(tr['name']))
                    if not segs_:
                        continue
                    n_it = int(math.ceil(horizon / tr['dur'])) + 1 if tr['iters'] == math.inf \
                        else int(math.ceil(tr['iters']))
                    for it in range(n_it):
                        base_t = tr['delay'] + it * tr['dur']
                        for a, b, _k in segs_:
                            t0 = base_t + a * tr['dur']
                            t1 = min(base_t + b * tr['dur'], tr['delay'] + tr['dur'] * tr['iters'])
                            if t1 > t0:
                                mov_iv.append((t0, t1))
                    kf_tf = {d.get('animation-timing-function', '').strip() for _p, d in keyframes.get(tr['name'], [])
                             if 'animation-timing-function' in d}
                    if (tr['linear'] and kf_tf <= {'linear'}) or (kf_tf and kf_tf <= {'linear'}):
                        run, r0, r1 = 0.0, None, None
                        for a, b, _k in sorted(segs_):
                            if r1 is not None and a <= r1 + 1e-6:
                                r1 = max(r1, b)
                            else:
                                r0, r1 = a, b
                            run = max(run, (r1 - r0) * tr['dur'] * min(tr['iters'], horizon / tr['dur'] + 1))
                        trace_run = max(trace_run, run)
            pass_len = cycle or horizon
            if control == 'loop':
                R.add('INFO', '[stillness]', 'exempt: control=loop has no answer step to pause before')
            elif not phase_marks or len(phase_marks) < 2:
                R.add('INFO', '[stillness]', 'exempt: fewer than two phase marks, no staged answer step to pause before')
            elif vb_ and vb_[0] == 'trace' and trace_run > pass_len / 2:
                R.add('INFO', '[stillness]', f'exempt: verb trace with a continuous linear move of {trace_run:.2f} s '
                      f'(more than half the {pass_len:g} s pass): a strip chart that never stops')
            else:
                last_mark = phase_marks[-1]
                merged = []
                for t0, t1 in sorted(iv for iv in mov_iv if iv[0] < last_mark - 1e-6):
                    if merged and t0 <= merged[-1][1] + 1e-6:
                        merged[-1][1] = max(merged[-1][1], t1)
                    else:
                        merged.append([t0, t1])
                # quiet windows inside the action part: after the first motion, followed by more motion
                gaps = [(merged[k][1], merged[k + 1][0]) for k in range(len(merged) - 1)]
                # the final burst: the last run of motion whose staggered parts follow within 0.3 s
                fb = len(merged) - 1
                # (never reaching back into an earlier phase: a piece that starts before the last phase's
                # mark, less 0.3 s, belongs to the steps before the answer)
                while fb > 0 and merged[fb][0] - merged[fb - 1][1] < 0.3 \
                        and merged[fb - 1][0] >= phase_marks[-2] - 0.3:
                    fb -= 1
                final_t = merged[fb][0] if merged else None
                still = gaps[fb - 1] if fb > 0 else None
                longest = max(gaps, key=lambda g: g[1] - g[0]) if gaps else None
                fix = ('end the earlier motion sooner, or move the phase mark, or lengthen the pass within 4 to 10 s '
                       'so 400 to 600 ms of nothing moving precede the answer step (motion-rules.md, stillness)')
                def win_(g):
                    return f'{round((g[1] - g[0]) * 1000):.0f} ms ({round(g[0], 3):g} to {round(g[1], 3):g} s)'
                if still and still[1] - still[0] >= 0.38:
                    R.ok('[stillness]', f'{win_(still)} with nothing moving before the final step at '
                         f'{round(final_t, 3):g} s')
                else:
                    lw = (f'the longest quiet window in the action part is {win_(longest)}' if longest
                          else 'no quiet window in the action part')
                    pre = (f'only {win_(still)} of stillness before the final step at {round(final_t, 3):g} s' if still
                           else f'no stillness: motion runs without a 0.3 s break from {round(final_t, 3):g} s into '
                                f'the last phase (mark {phase_marks[-2]:g} s)' if final_t is not None
                           else 'no motion before the last mark')
                    R.warn('[stillness]', f'{pre}; {lw}; {fix}',
                           wrapper['line'] if wrapper else None)

        GLOW_RE = re.compile(r'\b(blur|drop-shadow)\(', re.I)
        glow_rules = []
        for sel, body, pos, ctx in walk_rules(tree):
            if not acc(ctx):
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

        # ------------------------------------------------------------------ fade after fade (base only)
        # Entrance by kind (motion-rules.md): lines draw on, nodes land, areas reveal with a clip.
        # Among animated elements that are not text (nor groups holding only text), warn when at
        # least 5 animate and 80 % of them only fade (opacity, maybe with a small translate).
        if variant is None:
            TEXT_TAGS = ('text', 'tspan', 'textpath')
            SHAPE_TAGS = ('path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'use', 'image')

            def text_only(i):
                if E[i]['tag'] in TEXT_TAGS:
                    return True
                if E[i]['tag'] != 'g':
                    return False
                desc = [e for e in E if i in e['anc']]
                return any(e['tag'] in TEXT_TAGS for e in desc) and not any(e['tag'] in SHAPE_TAGS for e in desc)

            def fade_only(name):
                props = moving_props(name)
                if 'opacity' not in props or not props <= {'opacity', 'transform', 'translate'}:
                    return False
                for pct, d in keyframes.get(name, []):
                    for k in ('transform', 'translate'):
                        v = d.get(k)
                        if v is None or k not in props:
                            continue
                        if k == 'transform' and re.sub(r'translate[XY]?\([^)]*\)', '', v).strip() not in ('', 'none'):
                            return False
                        if any(abs(float(n)) > 24 for n in re.findall(r'-?\d*\.?\d+', re.sub(r'[A-Za-z]+\(|\)', ' ', v)
                                                                       .replace('px', ''))):
                            return False
                return True
            shapes = [i for i, ts in tracks.items() if not text_only(i)
                      and any(moving_props(tr['name']) for tr in ts)]
            fades = [i for i in shapes if all(fade_only(tr['name']) or not moving_props(tr['name'])
                                              for tr in tracks[i])]
            if len(shapes) >= 5 and len(fades) >= 0.8 * len(shapes):
                R.warn('[fade-after-fade]', f'{len(fades)} of {len(shapes)} animated shapes only fade in (opacity, at '
                       'most a small rise): nearly every shape only fades. Draw lines on (stroke-dashoffset), let '
                       'nodes land (scale 0.92 to 1 plus fade), reveal areas with a clip-path or mask in the '
                       'direction of meaning (motion-rules.md, entrance by kind)', E[fades[0]]['line'])
            elif shapes:
                R.ok('[fade-after-fade]', f'{len(fades)} of {len(shapes)} animated shapes only fade')

    R = R_main

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

    # ------------------------------------------------------------------ type: mono for data, type ladder
    # font-family and font-size of each text element, by the cascade (base rules, outside @media
    # and positive @supports) and inheritance; the font shorthand sets both.
    font_rules, order = [], 0
    for sel, body, pos, ctx in walk_rules(tree):
        if not all(re.match(r'@supports\s+not\b', ' '.join(c.split()), re.I) for c in ctx):
            continue
        dd = {}
        for p, v in decls(body):
            imp = '!important' in v
            v = v.replace('!important', '').strip()
            if p in ('font-family', 'font-size'):
                dd[p] = (v, imp)
            elif p == 'font':
                m = re.search(r'(?<![\w.-])(\d*\.?\d+(?:px|em|rem|%|pt)?)(?:\s*/\s*[\w.%]+)?\s+(.+)$', v)
                if m:
                    dd['font-size'], dd['font-family'] = (m.group(1), imp), (m.group(2).strip(), imp)
        if not dd:
            continue
        for s in split_selectors(sel):
            if gate_re and re.match(gate_re, s):
                s = re.sub('^' + gate_re, '', s)
            parsed, spec = parse_selector(s)
            if parsed:
                order += 1
                font_rules.append((parsed, spec, order, dd))
    fcache = {}

    def own_font(i, prop):
        if (i, prop) in fcache:
            return fcache[(i, prop)]
        el, best = E[i], None
        if prop in el['attrs']:
            best = ((0, 0, (-1, 0, 0), 0), el['attrs'][prop].strip())
        for parsed, spec, o, dd in font_rules:
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
        fcache[(i, prop)] = best[1] if best else None
        return fcache[(i, prop)]

    def font_of(i, prop):
        for j in [i] + list(reversed(E[i]['anc'])):
            v = own_font(j, prop)
            if v is not None and v.lower() != 'inherit':
                return v, j
        return None, None

    def size_px(i):
        """Font size of element i in viewBox px, or None when it cannot be told."""
        v, j = font_of(i, 'font-size')
        if v is None:
            return None
        m = re.fullmatch(r'(\d*\.?\d+)\s*(px)?', v)
        if m:
            return float(m.group(1))
        m = re.fullmatch(r'(\d*\.?\d+)\s*(em|%)', v)
        if m and E[j]['anc']:
            parent = size_px(E[j]['anc'][-1])
            if parent:
                return parent * float(m.group(1)) / (100 if m.group(2) == '%' else 1)
        return None

    TEXT_TAGS = ('text', 'tspan', 'textpath')
    texts = [i for i, e in enumerate(E) if e['tag'] in TEXT_TAGS and e['text'].strip()
             and not any(E[x]['tag'] in NO_RENDER for x in e['anc'])]
    # mono is for data: numbers, units, codes, timestamps, identifiers, formulas
    CODE_RE = re.compile(r'[_/=(%°+<>#@$€£{}\[\]|&*~×÷−±≤≥→←√∑∆Δ≈]|\w\.\w|:\s*\d|\b[A-Z]{2,}\b')
    UNITS = set('ms s min h d kg g mg µg km m cm mm µm nm kcal kj j kwh wh w kw mw hz khz mol l ml px pa kpa '
                'bar mbar mmhg ppm ppb db'.split())   # a unit on its own is data
    def math_symbol(t):
        """A mathematical symbol or constant: single Greek letters (π, Δ, μ), the set letters N Z Q R C used
        alone (also as ℕ ℤ ℚ ℝ ℂ), optionally joined by operators such as ⊂ ∈ ∪ ∩, or operators only."""
        s = t.replace(' ', '')
        if not s or re.search(r'[A-Za-z\u0370-\u03ff]{2}', s):
            return False  # two letters in a row make a word, not a symbol
        for ch in s:
            if not (unicodedata.category(ch) == 'Sm' or '\u0391' <= ch <= '\u03c9' or ch in 'ϑϕϖϵℕℤℚℝℂ∅∞∂∇·'
                    or ch in 'NZQRC'):
                return False
        return True
    costume = []
    for i in texts:
        fam, _ = font_of(i, 'font-family')
        if fam and '--anim-mono' in fam:
            t = ' '.join(E[i]['text'].split())
            if not any(ch.isdigit() for ch in t) and not CODE_RE.search(t) and t.lower() not in UNITS \
                    and not math_symbol(t):
                costume.append((i, t))
    if costume:
        shown = ', '.join(f'"{t[:30]}"' for _, t in costume[:3])
        R.warn('[mono-costume]', f'{len(costume)} mono text(s) with no digit and no code: {shown}'
               + (f' and {len(costume) - 3} more' if len(costume) > 3 else '') + '. Mono is for data (numbers, '
               'units, codes, timestamps, identifiers, formulas); set names, terms and group labels in '
               'var(--anim-font) at sub-label size in var(--anim-muted)', E[costume[0][0]]['line'])
    else:
        R.ok('[mono-costume]', 'mono text carries data only')
    # type ladder: any two sizes at least 1.25x apart (1.2 accepted for rounding), at most four sizes
    used = sorted({round(s, 2) for s in (size_px(i) for i in texts) if s})
    ladder = []
    for s in used:
        if ladder and s <= ladder[-1] * 1.02:
            continue
        ladder.append(s)
    close = [(a_, b_) for a_, b_ in zip(ladder, ladder[1:]) if b_ / a_ < 1.2]
    names = ', '.join(f'{s:g}' for s in reversed(ladder))
    if close or len(ladder) > 4:
        why = []
        if close:
            why.append('; '.join(f'{b_:g} and {a_:g} px are only {b_ / a_:.2f}x apart' for a_, b_ in close))
        if len(ladder) > 4:
            why.append(f'{len(ladder)} sizes, at most four')
        R.warn('[type-ladder]', f'text sizes {names} px: {"; ".join(why)}. Use the type ladder (at 1920: hero 56 '
               'to 96, label 24 to 30, sub-label 18 to 20, caption 24 to 28), any two sizes at least 1.25x apart: '
               'merge near sizes into one')
    elif ladder:
        R.ok('[type-ladder]', f'text sizes {names} px')

    # ------------------------------------------------------------------ focal element and node count
    focal = [e for e in E if 'data-anim-focal' in e['attrs']]
    if not focal:
        R.warn('[focal]', 'no data-anim-focal: mark the one element the eye lands on in the resting frame (the '
               'hero number or word, or the shape that is the claim) with data-anim-focal, on it or its group; '
               'make it about 1.5x a peer', wrapper['line'] if wrapper else None)
    elif len(focal) > 1:
        R.fail('[focal]', f'{len(focal)} elements carry data-anim-focal: exactly one focal element per fragment; '
               'keep it on the claim and drop it from the others', focal[1]['line'])
    else:
        R.ok('[focal]', f'one focal element: {describe(focal[0])}')
    # nodes are marked by the scaffolder's class <name>-node; hand-written fragments carry no marker
    nodes = [e for e in E if f'{name}-node' in e['attrs'].get('class', '').split()]
    if len(nodes) > 12:
        R.warn('[node-count]', f'{len(nodes)} nodes (class {name}-node): at most 12 in one figure; split the '
               'slide or keep a list', nodes[12]['line'])

    sys.exit(1 if R.print() else 0)


if __name__ == '__main__':
    main()
