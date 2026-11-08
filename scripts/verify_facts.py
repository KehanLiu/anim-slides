#!/usr/bin/env python3
"""Provenance gate: every number and label in a fragment must come from the source.

Usage:
  verify_facts.py FRAGMENT.html --source outline.json --slide N [--slide M | --slides 5-6]
  verify_facts.py FRAGMENT.html --source notes.md [--source more.txt]
  verify_facts.py FRAGMENT.html --source-text "the slide text"
                  [--slides A-B | --deck-wide] [--spec spec.yaml] [--allow terms.txt]
                  [--illustrative] [--strict] [--quiet-ok]

  --source        outline.json from extract_slides.py (needs --slide/--slides), or any text or
                  Markdown file (read whole). Repeatable.
  --slide         the primary slide(s): 7, 5-6 or 5,7,9 (repeatable). The corpus is each
                  slide's title, bullets, notes and table cells.
  --slides        context slides (neighbours, earlier builds); --deck-wide = every other
                  slide. Matches found only there are reported as "cross-slide" WARN.
  --source-text   literal source text. Repeatable.
  --spec          spec.yaml; its leading comment block is added to the corpus (the place to
                  transcribe figure data, e.g. "E0 (10 B$, 8%)"). Numbers found only there WARN.
  --allow         file with extra allowed terms, one per line (# comments allowed).
  --illustrative  number mismatches become WARN. Also switched on when the fragment's visible
                  text says "illustrative", "for illustration" or "example data/values".

Visible text = <text>/<tspan>, <title>, <desc>, aria-label, text in <foreignObject>, CSS
content: strings. Numbers are strict: each must match a source number (10B = $10 billion =
10 B$, 8% = 8 percent, 1993-95 = 1993-1995 = 1993 to 1995), be an axis tick (linear positions
on an evenly spaced grid), a structural index (1..k badges), a rounding of a source number,
or a simple derivation (a-b, a+b, a/b, percent change) of two source numbers, which is
reported. Anything else FAILs. Words are fuzzy (lowercase, simple stemming, small stop list);
unmatched words WARN per text element, capitalised terms, acronyms and codes separately as
"names". "splice" warns when a label joins words that never share one source bullet (meaning
added between them); "causal-slot" warns when text in a why/reason/cause slot (class or id)
comes from a bullet that states no cause. --strict makes these label findings FAIL.
Adjacent text runs (two <tspan>s, nested elements) are read with a space between them; when
that reading fails, the run-together form ('15<tspan>FTE', a word split across tspans) and a
de-hyphenated form are tried too, and the cleanest is kept. Soft hyphens are ignored. Source
words run together by an extractor ('FloorConsideration') also match split apart.
Output: OK / WARN / FAIL lines, then PASS or FAILED; exit code 1 on any FAIL.
verify_facts.py --self-test runs the built-in tests.
Standard library only.
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from html.parser import HTMLParser


# ----------------------------------------------------------------------------- reporting
class Report:
    def __init__(self):
        self.items = []

    def add(self, level, check, msg):
        self.items.append((level, check, msg))

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


# ----------------------------------------------------------------------------- fragment text
TEXT_TAGS = {'text', 'title', 'desc'}
SKIP_TAGS = {'style', 'script'}
SOFT = '\x00'  # a child-element boundary inside a text element: a space, or nothing
INVISIBLE_RE = re.compile('[\u00ad\u200b\u200c\u200d\u2060\ufeff]')  # &shy;, zero-width


def clean_text(s):
    """Drop soft hyphens and zero-width characters, collapse whitespace."""
    return re.sub(r'\s+', ' ', INVISIBLE_RE.sub('', s)).strip()


def dehyphen(s):
    """'Consid- eration' (a hyphen at a line break) -> 'Consideration'."""
    return re.sub(r'([a-z])-\s+([a-z])', r'\1\2', s)


class Elem:
    def __init__(self, tag, attrs, line):
        self.tag, self.attrs, self.line = tag, attrs, line
        self.parts, self.slot, self.depth = [], '', 0

    @property
    def text(self):
        """Spaced form: a space at every child-element boundary (two <tspan>s, nested
        elements), whitespace collapsed. The default for every check."""
        s = re.sub(SOFT + r'+(?=[,.;:!?)](?:\s|$|' + SOFT + '))', '', ''.join(self.parts))
        return clean_text(s.replace(SOFT, ' '))  # no space before trailing punctuation

    @property
    def variants(self):
        """Readings to try, best first: spaced; tight (child elements joined without a
        space: '15<tspan>FTE' or a word split across tspans); de-hyphenated (a word broken
        with a hyphen at a tspan line end). Duplicates dropped."""
        spaced = self.text
        tight = clean_text(''.join(self.parts).replace(SOFT, ''))
        out = [spaced, tight, dehyphen(spaced)]
        return list(dict.fromkeys(v for v in out if v))

    def where(self):
        cls = (self.attrs.get('class') or '').split()
        ident = self.attrs.get('id')
        tag = self.tag
        if ident:
            tag += '#' + ident
        elif cls:
            tag += '.' + cls[0]
        return f'{tag}, line {self.line}'


class FragmentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elems, self.cur, self.css, self.skip = [], None, [], None
        self.anc = []   # open ancestors: (tag, "class id")
        self.fo = 0     # depth inside foreignObject

    def _slot(self, a):
        return ' '.join(x for _, x in self.anc) + ' ' + (a.get('class') or '') + ' ' + (a.get('id') or '')

    def handle_startendtag(self, tag, attrs):
        self._open(tag, attrs, void=True)

    def handle_starttag(self, tag, attrs):
        self._open(tag, attrs, void=False)

    def _open(self, tag, attrs, void):
        a = dict(attrs)
        line = self.getpos()[0]
        if tag in SKIP_TAGS:
            if not void:
                self.skip = tag
            return
        if a.get('aria-label'):
            e = Elem('aria-label', a, line)
            e.slot = self._slot(a)
            e.parts.append(a['aria-label'])
            self.elems.append(e)
        if self.cur is None and (tag in TEXT_TAGS or self.fo):
            self.cur = Elem(tag if not self.fo else 'foreignObject/' + tag, a, line)
            self.cur.slot = self._slot(a)
            self.cur.depth = len(self.anc)
        elif self.cur is not None:
            if (tag == 'tspan' and 'x' in a) or tag in ('br', 'p', 'div', 'li'):
                self.cur.parts.append(' ')  # a new line inside the element
            else:
                self.cur.parts.append(SOFT)  # adjacent runs: try with and without a space
        if tag == 'foreignobject' and not void:
            self.fo += 1
        if not void:
            self.anc.append((tag, (a.get('class') or '') + ' ' + (a.get('id') or '')))

    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip:
                self.skip = None
            return
        if tag == 'foreignobject':
            self.fo = max(0, self.fo - 1)
        while self.anc:
            t, _ = self.anc.pop()
            if t == tag:
                break
        if self.cur is not None and len(self.anc) <= self.cur.depth:
            self.elems.append(self.cur)
            self.cur = None
        elif self.cur is not None:
            self.cur.parts.append(SOFT)  # end of a child element

    def handle_data(self, data):
        if self.skip:
            if self.skip == 'style':
                self.css.append((self.getpos()[0], data))
            return
        if self.cur is not None:
            self.cur.parts.append(data)


def fragment_elements(path):
    src = open(path, encoding='utf-8').read()
    p = FragmentParser()
    p.feed(src)
    p.close()
    elems = [e for e in p.elems if e.text]
    for line0, css in p.css:
        css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
        for m in re.finditer(r'content\s*:\s*(["\'])(.*?)\1', css):
            if m.group(2).strip():
                e = Elem('css-content', {}, line0 + css[:m.start()].count('\n'))
                pre = css[:m.start()]
                e.slot = pre[pre.rfind('}') + 1:]  # the rule's selector
                e.parts.append(m.group(2))
                elems.append(e)
    return elems


# ----------------------------------------------------------------------------- numbers
MAG = {'k': 1e3, 'thousand': 1e3, 'm': 1e6, 'mn': 1e6, 'million': 1e6, 'b': 1e9, 'bn': 1e9,
       'billion': 1e9, 't': 1e12, 'tn': 1e12, 'trillion': 1e12}
NUM_WORDS = {w: i for i, w in enumerate(
    'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen '
    'fifteen sixteen seventeen eighteen nineteen twenty'.split())}
NUM_WORDS.update({'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
                  'eighty': 80, 'ninety': 90, 'hundred': 100, 'dozen': 12})
NUM = r'\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+'
NUM_RE = re.compile(
    r'(?<![A-Za-z0-9.])(?P<cur>[$€£¥]\s?)?(?P<a>' + NUM + r')'
    r'(?:\s?[-–—]\s?(?P<cur2>[$€£¥])?(?P<b>' + NUM + r'))?'
    r'(?P<unit>\s?(?:%|percent\b|per cent\b|[x×](?![A-Za-z])|(?:st|nd|rd|th)\b|s\b|'
    r'(?:k|m|mn|b|bn|t|tn)(?:\s?[$€£])?(?![A-Za-z])|thousand\b|million\b|billion\b|trillion\b))?',
    re.I)
LABEL_RE = re.compile(r'\b(?:episodes?|steps?|phases?|stages?|slides?|chapters?|sections?|figures?|fig\.|no\.|#)'
                      r'\s*\d+(?:\s*(?:and|,|-|–|to|&)\s*\d+)*', re.I)
IDENT_RE = re.compile(r'\b[A-Za-z]+\d+[A-Za-z0-9]*\b')


class Num:
    def __init__(self, raw, value, pct=False, mag=None, cur=False, ratio=False, year_range=False):
        self.raw, self.value, self.pct, self.mag, self.cur, self.ratio = raw, value, pct, mag, cur, ratio
        self.year_range = year_range
        self.spelled = False
        self.label = False  # Episode 7, Step 3: a name, not a quantity

    @property
    def scaled(self):
        return self.value * self.mag if self.mag else self.value

    def decimals(self):
        m = re.search(r'\.(\d+)', self.raw)
        return len(m.group(1)) if m else 0


def _f(s):
    return float(s.replace(',', ''))


def numbers_in(text, spelled=True):
    """Return a list of Num found in text. Ranges give one Num per endpoint."""
    out = []
    for m in IDENT_RE.finditer(text):  # blank out codes like S0, CO2, Q3 (handled as names)
        text = text[:m.start()] + ' ' * (m.end() - m.start()) + text[m.end():]
    labels = [(m.start(), m.end()) for m in LABEL_RE.finditer(text)]
    for m in NUM_RE.finditer(text):
        unit = (m.group('unit') or '').strip().lower()
        pct = unit in ('%', 'percent', 'per cent')
        mag = None
        u = re.sub(r'[\s$€£]', '', unit)
        if u in MAG:
            mag = MAG[u]
        cur = bool(m.group('cur') or m.group('cur2') or re.search(r'[$€£]', unit))
        ratio = unit in ('x', '×')
        raw = m.group(0).strip()
        a = m.group('a')
        b = m.group('b')
        is_label = any(x <= m.start() < y for x, y in labels)
        if b:
            va, vb = _f(a), _f(b)
            yr = False
            if len(a) == 4 and len(b) == 2 and 1000 <= va <= 2999:  # 1993-95
                vb = float(a[:2] + b)
                yr = True
            elif len(a) == 4 and len(b) == 4:
                yr = True
            out.append(Num(raw, va, pct, mag, cur, ratio, yr))
            out.append(Num(raw, vb, pct, mag, cur, ratio, yr))
        else:
            out.append(Num(raw, _f(a), pct, mag, cur, ratio))
        if is_label:
            for x in out[-2 if b else -1:]:
                x.label = True
    if spelled:
        for m in re.finditer(r'[A-Za-z]+', text):
            w = m.group(0).lower()
            if w in NUM_WORDS and w != 'one':  # "one" is mostly a pronoun
                n = Num(m.group(0), float(NUM_WORDS[w]))
                n.spelled = True
                out.append(n)
    return out


def same(x, y):
    return abs(x - y) <= 1e-9 * max(1.0, abs(x), abs(y))


def fmt(v):
    return ('%g' % v) if abs(v) < 1e15 else str(v)


# ----------------------------------------------------------------------------- words
STOP = set('a an and or the then if yes no to of in on at by with step phase is are be for from '
           'as it its this that not vs per via but when while into through than up out both have has '
           'they them their who which also so can will was were been'.split())


def fold(s):
    s = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in s if not unicodedata.combining(c))


def stem(w):
    w = w.lower()
    for suf, rep in (('ies', 'y'), ('ing', ''), ('ed', ''), ('es', ''), ('s', '')):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)] + rep
    return w


WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*")


def words_in(text):
    return [w.rstrip("'").replace("'s", '') for w in WORD_RE.findall(fold(text))]


def word_match(st, stems, prefixes):
    if st in stems:
        return True
    # tolerant prefix match: approve / approval, regulate / regulation (5+ shared letters)
    if len(st) >= 5:
        return st[:5] in prefixes and any(
            len(os.path.commonprefix([st, s])) >= max(5, int(0.75 * min(len(st), len(s))))
            for s in prefixes[st[:5]])
    return False



# ----------------------------------------------------------------------------- source corpus
def parse_slides(specs):
    out = set()
    for spec in specs:
        for part in re.split(r'[,\s]+', spec.strip()):
            if not part:
                continue
            if re.fullmatch(r'\d+\s*-\s*\d+', part):
                a, b = (int(x) for x in part.split('-'))
                out.update(range(min(a, b), max(a, b) + 1))
            elif part.isdigit():
                out.add(int(part))
            else:
                sys.exit(f'verify_facts.py: bad slide number {part!r}')
    return sorted(out)


def slide_text(s):
    parts = [s.get('title') or '', *(s.get('bullets') or []), s.get('notes') or '', s.get('text') or '']
    for t in s.get('tables') or []:
        for row in t:
            parts.extend(c for c in row if c)
    parts.extend(s.get('mermaid') or [])
    return '\n'.join(parts)


def load_corpus(args, R):
    """Return a list of (label, tier, text); tier is primary, context or spec."""
    corpus = []
    primary = parse_slides(args.slide)
    context = [n for n in parse_slides(args.slides) if n not in primary]
    for path in args.source or []:
        try:
            raw = open(path, encoding='utf-8').read()
        except OSError as e:
            sys.exit(f'verify_facts.py: cannot read {path}: {e}')
        data = None
        if path.lower().endswith('.json'):
            try:
                data = json.loads(raw)
            except ValueError:
                data = None
        if isinstance(data, dict) and isinstance(data.get('slides'), list):
            if not primary:
                sys.exit('verify_facts.py: an outline.json source needs --slide N '
                         '(--slides A-B and --deck-wide only add context)')
            by = {s.get('index'): s for s in data['slides']}
            ctx = [n for n in by if n not in primary] if args.deck_wide else context
            for n in primary + sorted(ctx):
                if n not in by:
                    sys.exit(f'verify_facts.py: slide {n} not in {path}')
                corpus.append((f'slide {n}', 'primary' if n in primary else 'context', slide_text(by[n])))
            msg = f'{path}: slide {", ".join(map(str, primary))}'
            if ctx:
                msg += f'; context (reported as cross-slide): {len(ctx)} other slide{"s" if len(ctx) > 1 else ""}'
            R.add('OK', 'source', msg)
        else:
            corpus.append((os.path.basename(path), 'primary', raw))
            R.add('OK', 'source', f'{path}: whole file')
    for i, t in enumerate(args.source_text or []):
        corpus.append((f'source-text {i + 1}', 'primary', t))
    if args.spec:
        head = []
        for ln in open(args.spec, encoding='utf-8'):
            if ln.lstrip().startswith('#'):
                head.append(ln.lstrip()[1:])
            elif ln.strip():
                break
        if head:
            corpus.append(('spec header', 'spec', ''.join(head)))
            R.add('OK', 'source', f'{args.spec}: header comment ({len(head)} lines, reported as spec-only)')
    if args.allow:
        terms = [ln.split('#', 1)[0].strip() for ln in open(args.allow, encoding='utf-8')]
        corpus.append(('allow list', 'allow', '\n'.join(t for t in terms if t)))
    if not any(t == 'primary' for _, t, _ in corpus):
        sys.exit('verify_facts.py: give --source or --source-text')
    return corpus


JOINED_RE = re.compile(r'(?<=[a-z])(?=[A-Z][a-z])')


def with_splits(text):
    """Source text plus a copy of its run-together words split apart ('FloorConsideration',
    two text runs joined without a space -> also 'Floor Consideration'). Both forms are kept,
    so a real name like 'PowerPoint' still matches as written."""
    text = INVISIBLE_RE.sub('', text)
    joined = [w for w in re.findall(r'[A-Za-z]+', text) if JOINED_RE.search(w)]
    if not joined:
        return text
    return text + '\n' + ' '.join(JOINED_RE.sub(' ', w) for w in joined)


class Vocab:
    """Stems of one corpus tier, with a prefix index for tolerant matching."""

    def __init__(self):
        self.stems, self.prefixes = set(), {}

    def add_text(self, text):
        text = with_splits(text)
        for m in IDENT_RE.finditer(fold(text)):
            self.stems.add(m.group(0).lower())
        for w in words_in(text):
            st = stem(w)
            self.stems.add(st)
            if len(st) >= 5:
                self.prefixes.setdefault(st[:5], set()).add(st)

    def has(self, st, exact=False):
        return st in self.stems if exact else word_match(st, self.stems, self.prefixes)


def content_stems(text):
    return [stem(w) for w in words_in(IDENT_RE.sub(' ', fold(text)))
            if w.lower() not in STOP and len(w) >= 2 and w.lower() not in NUM_WORDS]


def source_units(text):
    """Units for co-occurrence checks: each bullet / line, and each pair of adjacent bullets
    (a timeline label often joins a step and its date). Returns (unit text, paragraph text)."""
    paras = [p.strip() for p in re.split(r'\n+', INVISIBLE_RE.sub('', text)) if p.strip()]
    out = []
    for i, p in enumerate(paras):
        out.append((p, p))
        if i + 1 < len(paras):
            out.append((p + ' / ' + paras[i + 1], p + ' ' + paras[i + 1]))
    return out


# ----------------------------------------------------------------------------- axis / index
def coord(e, k):
    v = e.attrs.get(k)
    try:
        return float(v.split()[0].split(',')[0]) if v else None
    except ValueError:
        return None


def bare_number(text):
    """Number value + unit kind when the element's whole text is one number, else None."""
    t = text.strip()
    if not re.fullmatch(r'[$€£¥]?\s?(' + NUM + r')\s?(%|[kKmMbB]|bn)?', t):
        return None
    ns = numbers_in(t, spelled=False)
    return (ns[0].value, 'pct' if ns[0].pct else ('cur' if ns[0].cur else 'plain')) if len(ns) == 1 else None


def axis_ticks(elems):
    """Elements whose number is a tick on a linear axis: same x (or same y) as >=2 others,
    position linear in value, and values on an evenly spaced grid covering >= 60 %.
    Returns {id(elem): description}."""
    cands = []
    for e in elems:
        if e.tag != 'text':
            continue
        b = bare_number(e.text)
        x, y = coord(e, 'x'), coord(e, 'y')
        if b and x is not None and y is not None:
            cands.append((e, b[0], b[1], x, y))
    found = {}
    for axis, fixed, var in (('x-axis', 4, 3), ('y-axis', 3, 4)):
        groups = {}
        for c in cands:
            groups.setdefault((c[2], round(c[fixed])), []).append(c)
        for (kind, pos), g in groups.items():
            pts = {}
            for c in g:
                pts.setdefault(c[1], c[var])
            if len(pts) < 3:
                continue
            vals = sorted(pts)
            # linear fit of position against value
            n = len(vals)
            mx = sum(vals) / n
            my = sum(pts[v] for v in vals) / n
            sxx = sum((v - mx) ** 2 for v in vals)
            if sxx == 0:
                continue
            k = sum((v - mx) * (pts[v] - my) for v in vals) / sxx
            span = abs(pts[vals[-1]] - pts[vals[0]]) or 1
            if k == 0 or max(abs(pts[v] - (my + k * (v - mx))) for v in vals) > 0.02 * span:
                continue
            diffs = [b - a for a, b in zip(vals, vals[1:])]
            step = min(diffs)
            if step <= 0 or any(abs(d / step - round(d / step)) > 1e-6 for d in diffs):
                continue
            grid = round((vals[-1] - vals[0]) / step) + 1
            if n / grid < 0.6:
                continue
            desc = f'{axis} at {pos}: {fmt(vals[0])}..{fmt(vals[-1])} step {fmt(step)}'
            for c in g:
                found[id(c[0])] = desc
    return found


INDEX_RE = re.compile(r'^(?:(?:step|phase|stage|episode|no\.?|#)\s*)?0?(\d{1,2})[.)]?$', re.I)


def structural_indices(elems):
    """Small integers used as badges (1, 2, 3 ... or Step 1, Step 2 ...): kept when the set is
    contiguous from 1 (or 0) with at least 2 members."""
    vals = {}
    for e in elems:
        m = INDEX_RE.match(e.text.strip())
        if m and e.tag in ('text', 'css-content'):
            vals.setdefault(int(m.group(1)), []).append(e)
    ks = sorted(vals)
    if len(ks) < 2:
        return set(), None
    start = 0 if ks[0] == 0 else 1
    run = []
    for i in range(start, 21):
        if i in vals:
            run.append(i)
        else:
            break
    if len(run) < 2:
        return set(), None
    return set(run), f'{run[0]}..{run[-1]}'


# ----------------------------------------------------------------------------- matching
def find_match(n, src):
    """src: list of (Num, label). Returns (status, detail)."""
    exact, loose = [], []
    for s, lab in src:
        if n.ratio and not s.ratio:
            continue  # "3x" needs a ratio in the source, or a derivation
        if n.mag and s.mag:
            ok = same(n.scaled, s.scaled)
        else:
            ok = same(n.value, s.value) or same(n.scaled, s.scaled) or same(n.value, s.scaled) \
                or same(n.scaled, s.value)
        if ok:
            (exact if (not n.pct or s.pct or not s.mag) else loose).append(lab)
    if exact:
        return 'ok', sorted(set(exact))
    if loose:
        return 'unit', sorted(set(loose))
    d = n.decimals()
    for s, lab in src:
        if s.decimals() > d and same(round(s.value, d), n.value):
            return 'rounded', f'{s.raw} ({lab})'
    return None, None


def derive(n, src):
    """Trivial derivations from two source numbers of one kind (both % or both plain):
    ratio for "3x" / "3 times", difference or percent change for "%", difference or sum
    otherwise. Years are never derived; results must agree within rounding and 3 %."""
    if 1000 <= n.value <= 2999 and float(n.value).is_integer() and not n.ratio:
        return None
    ratio = n.ratio or bool(re.search(r'times|fold', n.raw, re.I))
    vals = []
    for s, lab in src:
        if s.spelled or s.label:
            continue
        if s.value != 0 and (s.value, s.pct) not in [(v, p) for v, p, _ in vals]:
            vals.append((s.value, s.pct, s.raw))
    tol = 0.5 * 10 ** -n.decimals()
    for i, (a, pa, ra) in enumerate(vals):
        for b, pb, rb in vals[i + 1:]:
            if pa != pb:
                continue
            (hi, rh), (lo, rl) = ((a, ra), (b, rb)) if a >= b else ((b, rb), (a, ra))
            cands = []
            if ratio:
                cands.append((hi / lo, f'{rh} / {rl}'))
            elif n.pct:
                if pa:
                    cands.append((hi - lo, f'{rh} - {rl}'))
                cands.append(((hi - lo) / lo * 100, f'({rh} - {rl}) / {rl}'))
                cands.append(((hi - lo) / hi * 100, f'({rh} - {rl}) / {rh}'))
            elif n.value >= 2 and not pa:  # 0 and 1 are too easy to hit by accident
                cands.append((hi - lo, f'{rh} - {rl}'))
                cands.append((hi + lo, f'{rh} + {rl}'))
            for v, how in cands:
                if abs(v - n.value) <= tol + 1e-9 and abs(v - n.value) <= 0.03 * abs(n.value):
                    return f'{n.raw} = {how} = {fmt(round(v, n.decimals() + 2))}'
    return None


URL_RE = re.compile(r'(?:https?://|www\.)\S+|\S+@[\d.]+\S*')
ILLUS_RE = re.compile(r'\billustrative\b|\bfor illustration\b|\bexample (?:data|values|figures|numbers)\b|'
                      r'^\s*(?:example|e\.g\.)\s*$', re.I)
# slots that claim a cause or a category; and phrases that make such a claim in the source
CAUSAL_SLOT = re.compile(r'(?:^|[-_\s])(?:why|reason|reasons|cause|causes|because|legend|key|note|notes)'
                         r'(?:\d*|[-_]\w*)(?=\s|$)', re.I)
CAUSAL_PHRASE = re.compile(r'\b(?:because|due to|so that|so it|so they|leads? to|led to|causes?|caused|causing|'
                           r'in response to|as a result|result(?:s|ed)? in|therefore|thus|hence|owing to|'
                           r'in order to|to prevent|driven by|fear of|concerned)\b', re.I)
TIER_NAME = {'context': 'cross-slide', 'spec': 'spec-only', 'allow': 'spec-only'}


def slot_kind(e):
    m = CAUSAL_SLOT.search(e.slot.replace('.', ' '))
    if not m:
        return None
    k = re.sub(r'[-_\d\s]', ' ', m.group(0)).split()[0].lower()
    return {'reasons': 'reason', 'causes': 'cause', 'because': 'reason', 'key': 'legend',
            'notes': 'note'}.get(k, k)


# ----------------------------------------------------------------------------- main
def build_parser():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('fragment', nargs='?')
    ap.add_argument('--source', action='append')
    ap.add_argument('--slide', action='append', default=[])
    ap.add_argument('--slides', action='append', default=[])
    ap.add_argument('--deck-wide', action='store_true')
    ap.add_argument('--source-text', action='append')
    ap.add_argument('--spec')
    ap.add_argument('--allow')
    ap.add_argument('--illustrative', action='store_true')
    ap.add_argument('--strict', action='store_true',
                    help='word, name, splice, causal-slot and cross-slide findings on visible '
                         'labels FAIL instead of WARN (aria-label prose stays WARN)')
    ap.add_argument('--quiet-ok', action='store_true', help='print only WARN and FAIL lines')
    ap.add_argument('--self-test', action='store_true', help='run the built-in tests and exit')
    return ap


def best_variant(e, check):
    """Run check(text) -> (findings, *rest) on each reading of e (spaced, tight,
    de-hyphenated) and keep the first with the fewest FAIL, then WARN findings."""
    best, best_key = None, None
    for t in e.variants:
        res = check(t)
        key = (sum(1 for f in res[0] if f[0] == 'FAIL'), sum(1 for f in res[0] if f[0] == 'WARN'))
        if best is None or key < best_key:
            best, best_key = res, key
        if key == (0, 0):
            break
    return best


def verify(args):
    R = Report()
    corpus = load_corpus(args, R)
    elems = fragment_elements(args.fragment)
    if not elems:
        R.add('WARN', 'text', 'no visible text found in the fragment')

    tiers = ['primary', 'context', 'spec', 'allow']
    nums = {t: [] for t in tiers}
    vocab = {t: Vocab() for t in tiers}
    units = []  # (label, sentence, set of stems) of primary sources, for co-occurrence checks
    for lab, tier, text in corpus:
        ntext = URL_RE.sub(' ', INVISIBLE_RE.sub('', text))
        if tier == 'spec':  # "Slide 24" / "slides 5-6" in a header cite the source, not data
            ntext = re.sub(r'\bslides?\s+\d+(?:\s*[-–,]\s*\d+)*', ' ', ntext, flags=re.I)
        nums[tier].extend((n, lab) for n in numbers_in(ntext))
        vocab[tier].add_text(text)
        if tier == 'primary':
            for unit, para in source_units(text):
                units.append((lab, unit, set(content_stems(with_splits(unit))), para))

    illustrative = args.illustrative
    for e in elems:
        if any(ILLUS_RE.search(t) for t in e.variants):
            illustrative = True
            R.add('WARN', 'illustrative', f"fragment says \"{e.text[:60]}\" ({e.where()}): "
                  'number mismatches are downgraded to WARN')
            break
    else:
        if illustrative:
            R.add('WARN', 'illustrative', '--illustrative given: number mismatches are WARN; '
                  'the fragment itself must say the values are illustrative')

    ticks = axis_ticks(elems)
    idx_set, idx_desc = structural_indices(elems)
    all_src = [x for t in tiers for x in nums[t]]

    # ---- numbers
    def check_numbers(e, text):
        """Findings for the numbers in one reading of e: (findings, n_ok, axis, idx, outside)."""
        out, n_ok, axis, idx = [], 0, set(), False
        outs = {'cross-slide': [], 'spec-only': []}
        seen = set()
        for n in numbers_in(text):
            key = (n.raw, n.value)
            if key in seen:
                continue
            seen.add(key)
            where = f"in '{text[:70]}' ({e.where()})"
            st, det = find_match(n, nums['primary'])
            if st == 'ok':
                n_ok += 1
                continue
            if id(e) in ticks:
                axis.add(ticks[id(e)])
                continue
            m = INDEX_RE.match(text.strip())
            if m and int(m.group(1)) in idx_set and same(float(m.group(1)), n.value):
                idx = True
                continue
            if n.spelled and idx_set and same(n.value, max(idx_set)):
                idx = True  # "eight steps" with badges 1..8
                continue
            hit = None
            for t in tiers[1:]:
                st2, det2 = find_match(n, nums[t])
                if st2 == 'ok':
                    hit = (TIER_NAME[t], det2)
                    break
            if hit:
                outs[hit[0]].append(f'{n.raw} [{", ".join(hit[1])}]')
                continue
            st3, det3 = (st, det) if st else find_match(n, all_src)
            if st3 == 'unit':
                out.append(('WARN', 'numbers', f'{n.raw} {where}: the source has this value without % ({", ".join(det3)})'))
                continue
            if st3 == 'rounded':
                out.append(('WARN', 'numbers', f'{n.raw} {where}: rounded from {det3}'))
                continue
            how = derive(n, nums['primary'] + nums['spec'] + nums['allow'])
            if how:
                out.append(('WARN', 'derived', f'{how} {where}'))
                continue
            if n.spelled:
                out.append(('WARN', 'numbers', f'spelled-out "{n.raw}" {where}: not in the source; '
                            'fine for a count of what the fragment shows, otherwise a FAIL'))
                continue
            out.append(('WARN' if illustrative else 'FAIL', 'numbers',
                        f'{n.raw} {where}: not in the source' + (' (illustrative)' if illustrative else '')))
        # cross-slide / spec-only hits rank between a clean match and a finding
        ranked = out + [('WARN', '', '')] * (len(outs['cross-slide']) + len(outs['spec-only']))
        return ranked, out, n_ok, axis, idx, outs

    n_ok = 0
    outside = {'cross-slide': [], 'spec-only': []}
    axis_seen, idx_used, seen_txt = set(), False, set()
    for e in elems:
        if e.text in seen_txt:
            continue
        seen_txt.add(e.text)
        _, found, k, axis, idx, outs = best_variant(e, lambda t: check_numbers(e, t))
        for f in found:
            R.add(*f)
        n_ok += k
        axis_seen |= axis
        idx_used = idx_used or idx
        for kk in outside:
            outside[kk].extend(outs[kk])
    if n_ok:
        R.add('OK', 'numbers', f'{n_ok} number{"s" if n_ok > 1 else ""} found on the slide')
    for a in sorted(axis_seen):
        R.add('OK', 'axis', f'tick labels on a linear scale ({a})')
    if idx_used:
        R.add('OK', 'indices', f'structural step numbers {idx_desc}')
    if outside['cross-slide']:
        R.add('WARN', 'cross-slide', 'numbers found only on other slides, not the primary one: '
              + ', '.join(sorted(set(outside['cross-slide']))))
    if outside['spec-only']:
        R.add('WARN', 'spec-only', 'numbers found only in the spec header or allow list (an author\'s '
              'transcription of a figure: check it against the rendered slide): '
              + ', '.join(sorted(set(outside['spec-only']))))

    # ---- words, names, cross-slide words, sentence splices, causal slots
    def check_words(e, t):
        """Findings for the words of one reading t of e: (findings, words ok, words total)."""
        out, w_ok, w_total = [], 0, 0
        label = f"'{t[:60]}{'...' if len(t) > 60 else ''}' ({e.where()})"
        miss_w, miss_n, cross, spec_w = [], [], [], []
        ft = fold(t)
        for m in IDENT_RE.finditer(ft):
            w_total += 1
            c = m.group(0).lower()
            if c in vocab['primary'].stems:
                w_ok += 1
            elif c in vocab['context'].stems:
                cross.append(m.group(0))
            elif c in vocab['spec'].stems or c in vocab['allow'].stems:
                spec_w.append(m.group(0))
            else:
                miss_n.append(m.group(0))
        prim_stems = []
        # a word that exists only in a joined reading ('Consid'+'eration') must match exactly:
        # prefix tolerance would let 'Floor'+'Pancake' pass as a form of 'floor'
        spaced = {w.lower() for w in words_in(fold(e.text))}
        for i, w in enumerate(words_in(IDENT_RE.sub(' ', ft))):
            lw = w.lower()
            if lw in STOP or len(lw) < 2 or lw in NUM_WORDS:
                continue
            w_total += 1
            st = stem(lw)
            ex = lw not in spaced
            if vocab['primary'].has(st, ex):
                w_ok += 1
                prim_stems.append(st)
            elif vocab['context'].has(st, ex):
                cross.append(w)
            elif vocab['spec'].has(st, ex) or vocab['allow'].has(st, ex):
                spec_w.append(w)
            elif (len(w) >= 2 and w.isupper()) or (w[0].isupper() and i > 0):
                miss_n.append(w)
            else:
                miss_w.append(w)
        dd = lambda xs: ', '.join(dict.fromkeys(xs))  # noqa: E731
        if miss_n:
            out.append(('WARN', 'names', f'{label}: no source match for {dd(miss_n)}'))
        if miss_w:
            out.append(('WARN', 'words', f'{label}: no source match for {dd(miss_w)}'))
        if cross:
            out.append(('WARN', 'cross-slide', f'{label}: only on other slides: {dd(cross)}'))
        if spec_w and e.tag != 'aria-label':
            out.append(('WARN', 'spec-only', f'{label}: only in the spec header or allow list: {dd(spec_w)}'))
        if e.tag == 'aria-label' or not units:
            return out, w_ok, w_total
        # best supporting source sentence for this element
        want = set(prim_stems)
        best = max(units, key=lambda u: sum(1 for s_ in want if s_ in u[2] or
                                            any(word_match(s_, {x}, {x[:5]: {x}}) for x in u[2])))
        covered = {s_ for s_ in want if s_ in best[2] or
                   any(word_match(s_, {x}, {x[:5]: {x}}) for x in best[2])}
        if len(want) >= 3 and len(want - covered) >= 1 and len(covered) >= 2:
            out.append(('WARN', 'splice', f'{label}: closest source passage "{best[1][:80]}" ({best[0]}) '
                        f'lacks {dd(sorted(want - covered))}, taken from elsewhere: check the claim is the slide\'s'))
        kind = slot_kind(e)
        if kind and want and covered:
            own_causal = CAUSAL_PHRASE.search(t)
            if kind in ('note', 'legend') and not own_causal:
                return out, w_ok, w_total  # captions and categories: only a causal wording needs a causal source
            if not CAUSAL_PHRASE.search(best[3]):
                out.append(('WARN', 'causal-slot', f'{label} sits in a "{kind}" slot, but its source passage '
                            f'"{best[1][:80]}" ({best[0]}) states no cause (no because / due to / so / leads to)'))
        return out, w_ok, w_total

    seen_txt, w_ok, w_total = set(), 0, 0
    for e in elems:
        if (e.text, slot_kind(e)) in seen_txt:
            continue
        seen_txt.add((e.text, slot_kind(e)))
        found, k, tot = best_variant(e, lambda t: check_words(e, t))
        for f in found:
            R.add(*f)
        w_ok += k
        w_total += tot
    if w_total:
        R.add('OK', 'words', f'{w_ok} of {w_total} words match the primary source ({100 * w_ok // w_total}%)')

    if args.strict:
        hard = {'words', 'names', 'splice', 'causal-slot', 'cross-slide'}
        R.items = [('FAIL' if lvl == 'WARN' and chk in hard and '(aria-label' not in msg else lvl, chk, msg)
                   for lvl, chk, msg in R.items]
    if args.quiet_ok:
        R.items = [i for i in R.items if i[0] != 'OK']
    return R


# ----------------------------------------------------------------------------- self-test
SELF_TESTS = [
    # (name, fragment body, source text, expect no WARN/FAIL)
    ('two tspans', '<text x="0" y="0"><tspan>Floor</tspan><tspan>Consideration</tspan></text>',
     'Floor consideration of the bill', True),
    ('nested tspan with dy', '<text x="0" y="0">Floor<tspan dy="1.2em">Consideration'
     '<tspan dy="-0.4em">vote</tspan></tspan></text>', 'Floor consideration and a vote', True),
    ('word broken across tspans', '<text x="0" y="0">Consid<tspan class="b">eration</tspan> '
     'of the <tspan>15</tspan><tspan class="u">FTE</tspan></text>', 'Consideration took 15 FTE', True),
    ('soft hyphen and hyphen at a line end', '<text x="0" y="0">Consid&shy;eration '
     '<tspan x="0" dy="1em">appro-</tspan><tspan x="0" dy="1em">priation</tspan></text>',
     'Consideration of the appropriation', True),
    ('source runs joined', '<text x="0" y="0"><tspan>Floor</tspan> <tspan>Consideration</tspan></text>',
     'FloorConsideration', True),
    ('unrelated words still warn', '<text x="0" y="0"><tspan>Floor</tspan><tspan>Pancake</tspan></text>',
     'Floor consideration', False),
]


def self_test():
    import tempfile
    fails = 0
    with tempfile.TemporaryDirectory(prefix='verify-facts-test.') as tmp:
        def run(body, extra):
            frag = os.path.join(tmp, 'f.html')
            with open(frag, 'w', encoding='utf-8') as fh:
                fh.write('<svg viewBox="0 0 100 100">' + body + '</svg>')
            R = verify(build_parser().parse_args([frag, *extra]))
            return [i for i in R.items if i[0] != 'OK']

        cases = [(n, b, ['--source-text', s], ok) for n, b, s, ok in SELF_TESTS]
        outline = os.path.join(tmp, 'outline.json')
        with open(outline, 'w', encoding='utf-8') as fh:
            json.dump({'slides': [{'index': 1, 'title': 'Senate procedure',
                                   'bullets': ['Committee markup', 'Floor', 'Consideration of the bill',
                                               'Conference report, 3 days']}]}, fh)
        cases.append(('outline bullets', '<text x="0" y="0"><tspan>Floor</tspan><tspan dy="1em">'
                      'Consideration</tspan></text><text x="0" y="20">Conference <tspan>report</tspan>: '
                      '<tspan>3</tspan> days</text>', ['--source', outline, '--slide', '1'], True))
        for name, body, extra, want_clean in cases:
            bad = run(body, extra)
            ok = (not bad) == want_clean
            fails += not ok
            print(f'{"ok  " if ok else "FAIL"} {name}' + ('' if ok else f': {bad}'))
    print('self-test: ' + ('all passed' if not fails else f'{fails} failed'))
    return 1 if fails else 0


def main():
    args = build_parser().parse_args()
    if args.self_test:
        sys.exit(self_test())
    if not args.fragment:
        sys.exit('verify_facts.py: give FRAGMENT.html (or --self-test)')
    sys.exit(1 if verify(args).print() else 0)


if __name__ == '__main__':
    main()
