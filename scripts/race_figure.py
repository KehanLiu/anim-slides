#!/usr/bin/env python3
"""Duration race: two to six durations as bars that grow at one rate on one time axis.

Usage:
  race_figure.py SPEC.yaml -o FRAGMENT.html [--rendered-width PX] [--stage-width PX] [--no-check]
  (scaffold_from_spec.py calls this for `archetype: durations`.)

The spec holds what the slide says: each thing's label, its duration and unit, and the slide's
own takeaway sentence when it has one (references/spec-format.md, "Durations"). Everything
drawn is computed from those values in one pass, so a changed value changes the bar lengths,
the axis, the moment each bar stops, the bracket and the takeaway number together:

  geometry   one scale for every bar: x = x0 + px_per_unit * value, axis end on a round tick
  timing     every bar starts together and grows at the same speed, so a bar's run time is
             proportional to its value and the bars are equally long at every instant
  takeaway   the difference or the ratio of the two compared bars, computed, never typed
  claim      the slide's own sentence is the closing caption. Each number in it must follow
             from the values; a sentence left stale by a changed value stops the build (exit 1)

Units convert exactly inside ms/s/min/h/days/weeks and inside months/years. Crossing between
the two families needs `calendar: {month: 30}` (days) in the spec, and the figure says so.
A fragment made here is final: change the spec and build again, do not edit the fragment.
Standard library only (PyYAML is used when installed).
"""
import argparse
import math
import os
import re
import subprocess
import sys
import tempfile
from html import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# seconds per unit (clock family) and months per unit (calendar family)
CLOCK = {'ms': 0.001, 's': 1, 'min': 60, 'h': 3600, 'days': 86400, 'weeks': 604800}
CALENDAR = {'months': 1, 'years': 12}
ALIASES = {
    'ms': 'ms', 'millisecond': 'ms', 'milliseconds': 'ms',
    's': 's', 'sec': 's', 'secs': 's', 'second': 's', 'seconds': 's',
    'min': 'min', 'mins': 'min', 'minute': 'min', 'minutes': 'min',
    'h': 'h', 'hr': 'h', 'hrs': 'h', 'hour': 'h', 'hours': 'h',
    'd': 'days', 'day': 'days', 'days': 'days',
    'w': 'weeks', 'wk': 'weeks', 'wks': 'weeks', 'week': 'weeks', 'weeks': 'weeks',
    'mo': 'months', 'mos': 'months', 'month': 'months', 'months': 'months',
    'y': 'years', 'yr': 'years', 'yrs': 'years', 'year': 'years', 'years': 'years',
}
LONG = {'ms': 'milliseconds', 's': 'seconds', 'min': 'minutes', 'h': 'hours'}
SINGULAR = {'days': 'day', 'weeks': 'week', 'months': 'month', 'years': 'year', 'hours': 'hour',
            'minutes': 'minute', 'seconds': 'second', 'milliseconds': 'millisecond'}
WORD_NUM = {'half': 0.5, 'twice': 2, 'double': 2, 'doubles': 2, 'triple': 3, 'triples': 3,
            'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
            'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12}
LOOSE = re.compile(r'\b(about|around|roughly|approximately|nearly|almost|circa|ca\.|some|over|under|'
                   r'more than|less than|up to)\s*$|[≈~]\s*$', re.I)
ENTER = 'cubic-bezier(0.16,1,0.3,1)'
EXIT = 'cubic-bezier(0.3,0,1,1)'
PAD = 40


class SpecError(Exception):
    pass


def num(v):
    """A number as a slide would write it: 3, 4.5, 0.25, 1,200."""
    if abs(v - round(v)) < 1e-9:
        v = int(round(v))
        return f'{v:,}' if abs(v) >= 10000 else str(v)
    for d in (1, 2, 3, 4):              # a value the source wrote to d decimals keeps them: 1.04, not 1
        if abs(v - round(v, d)) < 1e-9:
            return f'{v:,.{d}f}' if abs(v) >= 10000 else f'{v:.{d}f}'
    return f'{v:.2f}'.rstrip('0').rstrip('.') if abs(v) < 1 else f'{v:.1f}'.rstrip('0').rstrip('.')


def unit_word(unit, value=2):
    return SINGULAR.get(unit, unit) if abs(value - 1) < 1e-9 and unit in SINGULAR else unit


def tw(s, fs, mono=False):
    """Width estimate, wide enough for the Linux fallback fonts."""
    return len(s) * fs * (0.62 if mono else 0.6)


def wrap(text, fs, maxw, maxlines=2):
    lines, cur = [], ''
    for word in text.split():
        cand = f'{cur} {word}'.strip()
        if cur and tw(cand, fs) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    lines.append(cur)
    if len(lines) > maxlines:
        lines = lines[:maxlines - 1] + [' '.join(lines[maxlines - 1:])]
    return lines


def canon(unit):
    u = str(unit).strip().lower().rstrip('.')
    return ALIASES.get(u)


_NUMBER = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+'
_PART = re.compile(rf'({_NUMBER})\s*((?!and\b)[^\W\d_][^\s\d,;!?.+\-\u2212\u2013\u2014]*\.?)?\s*(?:,\s*|\band\b\s*)?', re.I)
_RANGE = re.compile(r'\b(?:to|through|thru|until|till|or|between|vs)\b|[\u2013\u2014]|\.\.|(?<=[\w.])\s*-\s*(?=[\d.])', re.I)


def parse_duration(value, unit, where):
    """-> [(number, canonical unit or the raw unit string)], as written.

    A text value is read whole or not at all: '45 min', '.5 s', '1,200 ms', and compound
    durations in falling units of one family ('1 h 30 min', '2 years and 3 months'). A sign, a
    range ('1 min to 3 min', '2-3 h') or anything left over is an error, never a guess."""
    if isinstance(value, bool):
        raise SpecError(f'{where}: cannot read a duration from {value!r}')
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise SpecError(f'{where}: cannot read a duration from {value!r}')
        if unit is None:
            raise SpecError(f'{where}: value {value} has no unit (give `unit:` on the bar or the spec)')
        return [(float(value), canon(unit) or str(unit).strip())]
    text = str(value).strip()
    if re.match(r'[-\u2212]', text):
        raise SpecError(f'{where}: {text!r} is negative; a duration is a length of time, longer than zero')
    if _RANGE.search(text):
        raise SpecError(f'{where}: {text!r} reads as a range or a choice; a bar has one length. Give the one '
                        'duration the slide means (or one bar per end of the range)')
    out, pos = [], 0
    while pos < len(text):
        m = _PART.match(text, pos)
        if not m or m.end() == pos:
            break
        out.append((float(m.group(1).replace(',', '')), m.group(2)))
        pos = m.end()
    if not out or pos < len(text):
        raise SpecError(f'{where}: cannot read a duration from {text!r}'
                        + (f' (stopped at {text[pos:]!r})' if out else '')
                        + '; write a number and a unit, e.g. "45 min", "0.5 s" or "1 h 30 min"')
    if len(out) == 1:
        n, u = out[0]
        u = u or unit
        if u is None:
            raise SpecError(f'{where}: {text!r} has no unit')
        return [(n, canon(u) or str(u).strip())]
    # compound: every part in a time unit of one family, largest first, each unit once
    parts, last = [], None
    for n, u in out:
        c = canon(u) if u else None
        if c is None:
            raise SpecError(f'{where}: {text!r} has several numbers; each needs a time unit ("1 h 30 min"). '
                            'A decimal is written with a point (1.5), a range is not one duration')
        size = (0, CLOCK[c]) if c in CLOCK else (1, CALENDAR[c])
        if last is not None and (size[0] != last[0] or size[1] >= last[1]):
            raise SpecError(f'{where}: {text!r} is not one compound duration (units must fall, each used once, '
                            'e.g. "1 h 30 min"); if it is a range or two durations, give the one the slide means')
        last = size
        parts.append((n, c))
    return parts


class Converter:
    def __init__(self, calendar):
        self.month_days = self.year_days = None
        cal = calendar or {}
        if not isinstance(cal, dict):
            raise SpecError('calendar: must be a mapping, e.g. {month: 30}')
        for k, v in cal.items():
            c = canon(k)
            if c == 'months':
                self.month_days = float(v)
            elif c == 'years':
                self.year_days = float(v)
            else:
                raise SpecError(f'calendar: unknown key {k!r} (use month and/or year, in days)')
        self.used = False

    def family(self, u):
        return 'clock' if u in CLOCK else 'calendar' if u in CALENDAR else None

    def seconds(self, v, u, where):
        if u in CLOCK:
            return v * CLOCK[u]
        self.used = True
        if u == 'years' and self.year_days:
            return v * self.year_days * 86400
        md = self.month_days or (self.year_days / 12 if self.year_days else None)
        if md is None:
            raise SpecError(f'{where}: {u} and a clock unit meet in one figure. Months and years have no '
                            'fixed length in days; add the length the slide means, e.g. '
                            '`calendar: {month: 30}` or `calendar: {year: 365}`')
        return v * CALENDAR[u] * md * 86400

    def to(self, v, u, target, where):
        if u == target:
            return v
        fu, ft = self.family(u), self.family(target)
        if fu is None or ft is None:
            raise SpecError(f'{where}: cannot convert {u!r} to {target!r}; write every duration in a '
                            'time unit (ms, s, min, h, days, weeks, months, years) or in one shared unit')
        if fu == ft == 'calendar':
            return v * CALENDAR[u] / CALENDAR[target]
        if fu == ft == 'clock':
            return v * CLOCK[u] / CLOCK[target]
        return self.seconds(v, u, where) / self.seconds(1, target, where)

    def note(self):
        if not self.used:
            return None
        if self.year_days and not self.month_days:
            return f'1 year = {num(self.year_days)} days'
        return f'1 month = {num(self.month_days)} days'


def load(path):
    from scaffold_from_spec import load_spec
    return load_spec(path)


def nice_axis(vmax):
    """Tick step and axis end: 4 to 9 ticks on round numbers."""
    best = None
    exp = math.floor(math.log10(vmax)) if vmax > 0 else 0
    for e in (exp - 1, exp, exp + 1):
        for m in (1, 2, 3, 5):
            step = m * 10 ** e
            n = math.ceil(vmax / step - 1e-9)
            if 3 <= n <= 9:
                waste = n * step - vmax
                cand = (abs(n - 6) + 4 * waste / vmax, step, n)
                if best is None or cand < best:
                    best = cand
    if best is None:
        return vmax, 1
    return best[1], best[2]


SHORTER_CUE = r'sav\w*|shorter|faster|quicker|sooner|earlier|less|fewer|cuts?|cutting|shav\w*|gain\w*|reduc\w*'
LONGER_CUE = r'longer|slower|later|more|extra|behind|adds?|added|additional|los[et]\w*'
PLAIN_CUE = r'difference|gap|apart|margin'
CUE = re.compile(rf'\b(?:(?P<s>{SHORTER_CUE})|(?P<l>{LONGER_CUE})|(?P<p>{PLAIN_CUE}))\b', re.I)
NOT_A_CUE = re.compile(r'\b(?:more|less|fewer)\s+than\b|\bno\s+(?:more|less)\b', re.I)
CLAUSE = re.compile(r'[,;:\u2013\u2014]|\b(?:but|while|whereas|and)\b', re.I)


def claim_numbers(text):
    """One dict per number a sentence states, digits or words: v, loose, shown, dec, at (offset),
    kind ('multiple', 'percent' or 'plain') and unit (the word after a plain number, or None)."""
    out = []
    for m in re.finditer(r'(?<![\w.])(\d[\d,]*(?:\.\d+)?)(\s*(?:%|percent|×|x\b|times|fold|-fold))?', text):
        raw, tail = m.group(1), (m.group(2) or '').strip()
        kind = 'plain' if not tail else 'percent' if tail in ('%', 'percent') else 'multiple'
        um = re.match(r'[\s-]*([A-Za-z]+)', text[m.end():]) if kind == 'plain' else None
        out.append(dict(v=float(raw.replace(',', '')), loose=bool(LOOSE.search(text[:m.start()])),
                        shown=(raw + ' ' + tail).strip(), dec=len(raw.split('.')[1]) if '.' in raw else 0,
                        at=m.start(), kind=kind, unit=um.group(1) if um else None))
    for m in re.finditer(r"\b([A-Za-z]+)\b", text):
        w = m.group(1).lower()
        if w in WORD_NUM and (w in ('half', 'twice', 'double', 'doubles', 'triple', 'triples')
                              or re.match(r'\s*(times|×|x\b|fold|-fold)', text[m.end():], re.I)):
            out.append(dict(v=WORD_NUM[w], loose=bool(LOOSE.search(text[:m.start()])), shown=m.group(1) + ' ×',
                            dec=0, at=m.start(), kind='multiple', unit=None))
    return out


def clause_of(text, at):
    """(start, end) of the clause around offset `at`."""
    a, b = 0, len(text)
    for m in CLAUSE.finditer(text):
        if m.end() <= at:
            a = m.end()
        elif m.start() > at:
            b = m.start()
            break
    return a, b


def near(a, b, decimals, loose):
    if loose:
        return abs(a - b) <= 0.1 * max(abs(b), 1e-9)
    return abs(a - b) <= 0.5 * 10 ** (-decimals) + 1e-9


class Fig:
    pass


def plan(sp, rendered=None, stage=1920):
    """Read the spec and compute every position, time and derived number. -> Fig"""
    if not isinstance(sp, dict):
        raise SpecError('the spec must be a mapping')
    F = Fig()
    F.name = str(sp.get('name', '')).strip()
    if not re.fullmatch(r'[a-z][a-z0-9-]{1,23}', F.name):
        raise SpecError('name: kebab-case, 2 to 24 characters')
    known = {'name', 'archetype', 'verb', 'unit', 'start', 'status', 'note', 'bars', 'takeaway', 'claim',
             'opening', 'calendar', 'size', 'control', 'title', 'compare'}
    extra = sorted(set(sp) - known)
    if extra:
        raise SpecError(f'unknown key(s) for archetype durations: {", ".join(extra)} (allowed: {", ".join(sorted(known))})')
    if sp.get('verb', 'race') != 'race':
        raise SpecError('archetype durations is drawn with verb race')
    if sp.get('control', 'once') != 'once':
        raise SpecError('archetype durations plays once (control: once)')
    bars = sp.get('bars')
    if not isinstance(bars, list) or not 2 <= len(bars) <= 6:
        raise SpecError('bars: two to six entries, each {label, value, unit}')
    conv = Converter(sp.get('calendar'))
    default_unit = sp.get('unit')
    F.status = str(sp.get('status', '')).strip().lower()
    if F.status not in ('real', 'illustrative'):
        raise SpecError('status: real (the durations are facts from the source) or illustrative '
                        '(example figures; the figure then says so)')

    B = []
    for i, b in enumerate(bars):
        where = f'bars[{i}]'
        if not isinstance(b, dict) or not str(b.get('label', '')).strip():
            raise SpecError(f'{where}: needs a label')
        x = Fig()
        x.label = str(b['label']).strip()
        x.end = str(b['end']).strip() if b.get('end') else None
        x.stages = []
        stages = b.get('stages') or []
        if 'value' not in b and not stages:
            raise SpecError(f'{where} ({x.label}): needs a value, or stages that add up to it')
        x.parts = parse_duration(b['value'], b.get('unit', default_unit), where) if 'value' in b else None
        x.shown = str(b['shown']).strip() if b.get('shown') else None
        x.raw_stages = stages
        x.unit_hint = b.get('unit', default_unit)
        B.append(x)

    # the axis unit: stated, else the unit of the first bar that has one
    axis = canon(default_unit) or (str(default_unit).strip() if default_unit else None)
    if axis is None:                    # the unit the longest bar is written in
        cands = [x.parts[0][1] for x in B if x.parts]
        if cands:
            axis = cands[0]
            try:
                axis = max((x for x in B if x.parts),
                           key=lambda x: sum(conv.to(n, u, cands[0], 'bars') for n, u in x.parts)).parts[0][1]
            except SpecError:
                pass
    if axis is None:
        raise SpecError('unit: name the axis unit')
    F.unit = axis
    F.time_unit = axis in CLOCK or axis in CALENDAR

    for i, x in enumerate(B):
        where = f'bars[{i}] ({x.label})'
        tot = 0
        for j, s in enumerate(x.raw_stages):
            if not isinstance(s, dict) or 'value' not in s or not str(s.get('label', '')).strip():
                raise SpecError(f'{where}: stages[{j}] needs label and value')
            parts = parse_duration(s['value'], s.get('unit', x.unit_hint or axis), f'{where} stages[{j}]')
            v = sum(conv.to(n, u, axis, where) for n, u in parts)
            if v <= 0:
                raise SpecError(f'{where}: stages[{j}] must be longer than zero')
            st = Fig()
            st.label, st.v, st.a = str(s['label']).strip(), v, tot
            st.shown = ' '.join(f'{num(n)} {unit_word(u, n)}' for n, u in parts)
            tot += v
            x.stages.append(st)
        if x.parts:
            x.v = sum(conv.to(n, u, axis, where) for n, u in x.parts)
            if x.stages and abs(tot - x.v) > 1e-6 * max(1, x.v):
                raise SpecError(f'{where}: the stages add up to {num(tot)} {axis}, the value says {num(x.v)} '
                                f'{axis}. Change one of them (or drop `value` and the total follows the stages)')
            if not x.shown:
                x.shown = ' '.join(f'{num(n)} {unit_word(u, n)}' for n, u in x.parts)
        else:
            x.v = tot
            x.shown = x.shown or f'{num(tot)} {unit_word(axis, tot)}'
        if x.v <= 0:
            raise SpecError(f'{where}: a duration must be longer than zero')
    F.bars = B
    F.conv_note = conv.note()
    vmax = max(x.v for x in B)

    # ---- which two bars the takeaway compares
    cmp_ = sp.get('compare')
    by_label = {x.label.lower(): x for x in B}
    if cmp_:
        if not isinstance(cmp_, list) or len(cmp_) != 2 or any(str(c).lower() not in by_label for c in cmp_):
            raise SpecError('compare: two bar labels, e.g. [court trial, mediation]')
        p, q = (by_label[str(c).lower()] for c in cmp_)
        F.long, F.short = (p, q) if p.v >= q.v else (q, p)
    else:
        F.long = max(B, key=lambda x: x.v)
        F.short = min(B, key=lambda x: x.v)
    F.diff = F.long.v - F.short.v
    F.ratio = F.long.v / F.short.v
    F.claim = str(sp['claim']).strip() if sp.get('claim') else None
    F.opening = str(sp['opening']).strip() if sp.get('opening') else None
    F.start = str(sp['start']).strip() if sp.get('start') else None
    F.note = str(sp['note']).strip() if sp.get('note') else None

    # ---- the claim: every number in the slide's sentence is bound to what it says about the
    # values. A multiple must be a ratio, a percentage a percentage, a duration beside a
    # comparing word (saves, longer, faster ...) a difference in that unit, any other duration
    # a bar's or a stage's own length. What cannot be tied down is flagged for review.
    pct = [('percent shorter', 100 * F.diff / F.long.v), ('percent longer', 100 * F.diff / F.short.v),
           ('share', 100 * F.short.v / F.long.v)]
    ratios, diffs, values = [('ratio', F.ratio)], [('difference', F.diff, F.long, F.short)], []
    for x in B:
        values.append((x.label, x.v, axis, x))
        values += [(x.label, n, u, x) for n, u in (x.parts or [])]
        values += [(s.label, s.v, axis, x) for s in x.stages]
    for p in B:
        for q in B:
            if p is not q and p.v > q.v:
                diffs.append((f'{p.label} minus {q.label}', p.v - q.v, p, q))
                ratios += [(f'{p.label} / {q.label}', p.v / q.v), (f'{q.label} / {p.label}', q.v / p.v)]
                pct += [(f'{q.label} shorter than {p.label}', 100 * (p.v - q.v) / p.v),
                        (f'{p.label} longer than {q.label}', 100 * (p.v - q.v) / q.v),
                        (f'{q.label} as a share of {p.label}', 100 * q.v / p.v)]
    claim_kind = None
    F.claim_review = []
    if F.claim:
        stale = []
        low = F.claim.lower()
        blanked = NOT_A_CUE.sub(lambda m: ' ' * len(m.group(0)), F.claim)
        mentions = sorted((m.start(), x) for x in B for m in re.finditer(re.escape(x.label.lower()), low))

        def in_unit(v, cu):                         # an axis value in the claim's unit
            return v if cu in (None, axis) else conv.to(v, axis, cu, 'claim')

        stated = claim_numbers(F.claim)
        # "about 3 months, the trial after about 18": a number without a unit takes the one unit
        # the sentence states elsewhere; with two different units nothing is assumed
        one_unit = {canon(c['unit']) for c in stated if c['kind'] == 'plain' and c['unit'] and canon(c['unit'])}
        for c in stated:
            v, loose, shown, dec = c['v'], c['loose'], c['shown'], c['dec']
            if c['kind'] == 'multiple':
                hit = [k for k, a in ratios if near(v, a, dec, loose)]
                if not hit:
                    stale.append(shown)
                elif claim_kind is None and hit[0] == 'ratio':
                    claim_kind = 'ratio'
                continue
            if c['kind'] == 'percent':
                if not any(near(v, a, dec, loose) for _, a in pct):
                    stale.append(shown)
                continue
            cu = canon(c['unit']) if c['unit'] else None
            if cu is None and c['unit'] and c['unit'].lower() == str(axis).lower():
                cu = axis
            if cu and cu != axis and not (F.time_unit and (cu in CLOCK or cu in CALENDAR)):
                cu = None
            said = f'{shown} {c["unit"]}' if cu else shown
            follows = (c['unit'] or '').lower()
            if cu is None and len(one_unit) == 1 and F.time_unit and follows in ('', 'to', 'and', 'or', 'vs', 'versus', 'against'):
                cu = next(iter(one_unit))
            if cu is None and follows and abs(v - len(B)) < 1e-9:
                continue                            # "2 routes": the count of bars
            if cu is None:                          # a bare number: nothing says what it measures
                if any(near(v, a, dec, loose) for a in [len(B)] + [d[1] for d in diffs] + [w[1] for w in values]):
                    F.claim_review.append(f'"{shown}" has no unit beside it, so it could not be tied to a '
                                          'duration or a difference')
                else:
                    stale.append(shown)
                continue
            a0, a1 = clause_of(blanked, c['at'])
            cue = CUE.search(blanked, a0, a1)
            try:
                d_hit = [d for d in diffs if near(v, in_unit(d[1], cu), dec, loose)]
                v_hit = [w for w in values if near(v, in_unit(w[1], cu) if w[2] == axis else conv.to(w[1], w[2], cu, 'claim'), dec, loose)]
            except SpecError:
                d_hit, v_hit = [], []
            if cue:                                 # "saves 14 minutes", "30 minutes longer": a difference
                if not d_hit:
                    stale.append(said)
                    continue
                if claim_kind is None and d_hit[0][0] == 'difference':
                    claim_kind = 'difference'
                subj = [x for at, x in mentions if at < cue.start()]
                if subj and not cue.group('p'):
                    want_long = bool(cue.group('l'))
                    if not any((d[2] if want_long else d[3]) is subj[-1] for d in d_hit):
                        F.claim_review.append(
                            f'"{said}" follows "{cue.group(0)}", and the bar named just before it is '
                            f'{subj[-1].label}, which is the {"shorter" if want_long else "longer"} one here: '
                            'check the direction of the sentence')
            elif v_hit:                             # "takes 15 minutes": a bar's or a stage's own length
                named = [x for at, x in mentions if a0 <= at < a1]
                if named and not any(w[3] in named for w in v_hit):
                    F.claim_review.append(f'"{said}" stands beside {named[0].label}, but it is the length of '
                                          f'{v_hit[0][0]}: check which bar the sentence means')
            elif d_hit:
                F.claim_review.append(f'"{said}" equals a difference between two bars, but no comparing word '
                                      '(saves, longer, faster ...) stands beside it')
            else:
                stale.append(said)
        if stale:
            raise SpecError(
                f'claim: the sentence says {", ".join(stale)}, which no longer follows from the values. '
                f'{F.long.label} {num(F.long.v)} {axis}, {F.short.label} {num(F.short.v)} {axis}: '
                f'difference {num(F.diff)} {axis}, ratio {num(F.ratio)}×, '
                f'{num(100 * F.diff / F.long.v)} % shorter. Reword the claim with the numbers that hold '
                '(and tell the user the slide sentence changed), then build again')

    tk = sp.get('takeaway', 'auto')
    words = None
    if isinstance(tk, dict):
        words = tk.get('words')
        tk = tk.get('kind', 'auto')
    tk = str(tk).lower()
    if tk not in ('auto', 'difference', 'ratio', 'none'):
        raise SpecError('takeaway: auto, difference, ratio or none')
    if tk == 'auto':
        tk = claim_kind or ('ratio' if F.ratio >= 3 else 'difference')
    if F.diff <= 1e-9 * vmax:
        tk = 'none'
    F.kind = tk
    if tk == 'difference':
        F.hero = num(F.diff)
        F.hero_words = words or f'{unit_word(LONG.get(axis, axis), F.diff)} longer'
    elif tk == 'ratio':
        r = F.ratio
        exact = abs(r - round(r, 1)) < 1e-9
        shown = num(round(r)) if r >= 20 and not exact else num(round(r, 1))
        F.hero = f'{shown}×'
        F.hero_words = words or ('as long' if abs(float(shown.replace(",", "")) - r) < 1e-9 else 'as long, rounded')
    else:
        F.hero = F.hero_words = None

    # ---- geometry. One viewBox unit is one stage pixel when the slot width is known.
    size = sp.get('size')
    if size:
        W = int(size[0])
    elif rendered:
        W = int(round(rendered * 1920 / stage))
    else:
        W = 1680
    if W < 900:
        raise SpecError(f'the figure is {W} px wide at stage scale; a duration race needs 900 px or more')
    F.W = W
    F.fs = dict(hero=72, row=30, lbl=24, sub=18, note=24)
    fs = F.fs
    lab_w = min(300, max(tw(x.label, fs['row']) for x in B))
    for x in B:
        x.lab = wrap(x.label, fs['row'], lab_w + 1)
    lab_w = max(tw(l, fs['row']) for x in B for l in x.lab)
    x0 = max(PAD + lab_w + 24, 200)
    if F.start:
        x0 = max(x0, PAD + tw(F.start, fs['lbl']) / 2)
    for x in B:
        x.end_w = max(tw(x.end, fs['lbl']) if x.end else 0, tw(x.shown, fs['lbl'] if not x.end else fs['sub'], True))
    step, nt = nice_axis(vmax)
    amax = step * nt
    unit_w = tw(LONG.get(F.unit, F.unit), fs['sub']) + 30
    scale = min([(W - PAD - 20 - x.end_w - x0) / x.v for x in B] + [(W - PAD - unit_w - x0) / amax])
    if scale * vmax < 300:
        raise SpecError('the labels leave less than 300 px for the longest bar; shorten the labels or widen the slot')
    F.x0, F.scale, F.step, F.nt, F.amax = x0, scale, step, nt, amax
    X = lambda v: x0 + scale * v                                             # noqa: E731
    F.X = X

    notes = [n for n in (F.note, ' · '.join(
        [f'bar length shows {LONG.get(F.unit, F.unit)}', 'one scale for every bar'] + ([F.conv_note] if F.conv_note else []))) if n]
    F.notes = notes
    y = 38 + 26 * (len(notes) - 1)
    top = y + (60 if F.start else 36)
    F.top = top
    F.boxes = []                                    # text boxes that gridlines and guides keep clear of
    BH = 56
    yb = top + 16
    for x in B:
        x.y = yb
        # stage labels fit under the bar when each has room before the next one starts
        x.stage_mode = None
        if x.stages:
            ok, lines_max = True, 1
            for j, s in enumerate(x.stages):
                room = (X(x.stages[j + 1].a) if j + 1 < len(x.stages) else W - PAD) - X(s.a) - 24
                s.lines = wrap(s.label, fs['lbl'], room)
                s.w = max([tw(l, fs['lbl']) for l in s.lines] + [tw(s.shown, fs['sub'], True)])
                if s.w > room:
                    ok = False
                lines_max = max(lines_max, len(s.lines))
            x.stage_mode = 'under' if ok else 'caption'
            x.stage_lines = lines_max
        x.bottom = yb + BH + ((50 + 28 * (x.stage_lines - 1) + 26 + 14) if x.stage_mode == 'under' else 0)
        lh = 34
        ly = yb + BH / 2 + 10 - lh * (len(x.lab) - 1) / 2
        x.lab_y = ly
        ex = X(x.v) + 20
        F.boxes.append((ex - 6, yb - 6, ex + x.end_w + 6, yb + BH + 6))
        if x.stage_mode == 'under':
            for s in x.stages:
                F.boxes.append((X(s.a) + 6, yb + BH + 24, X(s.a) + 12 + s.w + 6, x.bottom))
        yb = x.bottom + 62
    last = B[-1].bottom
    if F.kind != 'none':
        F.yb = last + 40
        F.yh = F.yb + 26 + 56
        hw = tw(F.hero, fs['hero']) * 0.95
        ww = tw(F.hero_words, fs['row'])
        mid = (X(F.short.v) + X(F.long.v)) / 2
        hx = min(max(mid - (hw + 14 + ww) / 2, x0 + 12), W - PAD - hw - 14 - ww)
        F.hx, F.hw = hx + hw, hw                    # the number is right-aligned at hx + hw
        F.boxes.append((hx - 10, F.yh - 62, hx + hw + 14 + ww + 10, F.yh + 16))
        F.ya = F.yh + 44
    else:
        F.ya = last + 44
    F.caps = []                                     # (text, in, out) filled by the timing below
    mids = []
    for x in B:
        if x.stage_mode == 'caption':
            vals = {round(s.v, 9) for s in x.stages}
            if len(vals) == 1:
                one = x.stages[0]
                mids.append(f'{x.label}: {", ".join(s.label for s in x.stages)}, {one.shown} each')
            else:
                mids.append(f'{x.label}: ' + ', '.join(f'{s.label} {s.shown}' for s in x.stages))
    F.mid = ' · '.join(mids) if mids else None
    has_cap = bool(F.claim or F.opening or F.mid)
    for c in (F.claim, F.opening, F.mid):
        if c and tw(c, fs['note']) > W - 2 * PAD:
            raise SpecError(f'a caption is wider than the figure at 24 px: {c!r}. Shorten it'
                            + (' (stage names that do not fit under their bar are listed in a caption)' if c == F.mid else ''))
    F.yc = F.ya + 36 + 74 if has_cap else None
    H = int(round((F.yc + 40) if has_cap else (F.ya + 36 + 30)))
    if size and int(size[1]) > H:                   # a taller slot: centre the figure in it
        F.dy = (int(size[1]) - H) / 2
        H = int(size[1])
    else:
        F.dy = 0
    F.H = H

    # ---- timing: one speed for every bar, so run time is proportional to the value
    any_under = any(x.stage_mode == 'under' for x in B)
    RL = 4.0 if any_under else 3.2
    T0 = 0.5
    F.speed = vmax / RL                              # axis units per second
    for x in B:
        x.t1 = T0 + RL * x.v / vmax
        for s in x.stages:
            s.t = T0 + RL * s.a / vmax
    race_end = T0 + RL + 0.08 + 0.35
    F.T0, F.RL, F.race_end = T0, RL, race_end
    ta = race_end + 0.47
    F.ta = ta
    if F.kind != 'none':
        F.end = round(ta + 1.1 + 1.4, 1)
        F.marks = [0.45, round(race_end + 0.07, 2), round(ta + 1.1, 2)]
    else:
        F.end = round(ta + 0.5 + 1.4, 1)
        F.marks = [0.45, round(race_end + 0.07, 2)]
    return F


def pc(t, F):
    return f'{100 * t / F.end:.3f}'.rstrip('0').rstrip('.') + '%'


def fade(name, t, d, F, rise=0, out=None):
    """An enter (and optional exit) keyframe block."""
    a = f'opacity:0;transform:translateY({rise}px)' if rise else 'opacity:0'
    b = 'opacity:1;transform:translateY(0)' if rise else 'opacity:1'
    k = [f'0%{{{a}}}'] if t > 0.0005 else []
    k.append(f'{pc(t, F)}{{{a};animation-timing-function:{ENTER}}}')
    k.append(f'{pc(t + d, F)}{{{b}}}')
    if out is not None:
        k.append(f'{pc(out, F)}{{{b};animation-timing-function:{EXIT}}}')
        k.append(f'{pc(out + 0.2, F)}{{{a if not rise else "opacity:0;transform:translateY(0)"}}}')
        k.append(f'100%{{{a if not rise else "opacity:0;transform:translateY(0)"}}}')
    else:
        k.append(f'100%{{{b}}}')
    return f'@keyframes {name}{{{"".join(k)}}}'


def cut(x, y0, y1, boxes):
    """Vertical line at x from y0 to y1 as path segments that keep clear of the text boxes."""
    spans = sorted((b[1], b[3]) for b in boxes if b[0] <= x <= b[2] and b[3] > y0 and b[1] < y1)
    out, y = [], y0
    for a, b in spans:
        if a - y > 60:
            out.append(f'M{x:.1f} {y:.1f} V{a:.1f}')
        y = max(y, b)
    if y1 - y > 60:
        out.append(f'M{x:.1f} {y:.1f} V{y1:.1f}')
    return ' '.join(out)


def render(F, spec_name='spec.yaml'):
    N, W, H, fs, X = F.name, F.W, F.H, F.fs, F.X
    P = f'.anim-{N} .{N}-'
    x0, B = F.x0, F.bars
    e = lambda s: escape(str(s), quote=False)                                # noqa: E731
    ya, BH = F.ya, 56
    kf, run, body = [], [], []

    def animate(cls, name=None):
        run.append(f'.visible .anim-{N} .{N}-{cls}{{animation:{N}-{name or cls} {F.end}s linear 1 both}}')

    # ---- facts, for the reader of the file and for verify_facts.py
    facts = [f'<!-- {N} (archetype durations, verb race). Generated by scripts/race_figure.py from {spec_name}.',
             '  Do not edit this file: change a value in the spec and build again, so the bars, the axis,',
             '  the timing and the takeaway stay in step.',
             f'  Scale: 1 {unit_word(F.unit, 1)} = {F.scale:.3f} px for every bar (x = {x0:.1f} + {F.scale:.3f} * value). '
             f'Speed: {num(round(F.speed, 3))} {F.unit} per second for every bar.',
             '  Facts:']
    for x in B:
        facts.append(f'  - {x.label}: {x.shown}' + (f' = {num(x.v)} {F.unit}' if x.shown != f"{num(x.v)} {unit_word(F.unit, x.v)}" else '')
                     + (': ILLUSTRATIVE' if F.status == 'illustrative' else ': from the slide')
                     + f'; bar {F.scale * x.v:.1f} px, stops at {x.t1:.3f} s')
        for s in x.stages:
            facts.append(f'    - {s.label}: {s.shown}')
    if F.conv_note:
        facts.append(f'  - {F.conv_note}: the conversion the spec states')
    if F.kind == 'difference':
        facts.append(f'  - "{F.hero} {F.hero_words}" = {num(F.long.v)} - {num(F.short.v)}: arithmetic on the values above')
    elif F.kind == 'ratio':
        facts.append(f'  - "{F.hero} {F.hero_words}" = {num(F.long.v)} / {num(F.short.v)} = {F.ratio:.4g}: arithmetic on the values above')
    if F.claim:
        facts.append('  - closing caption: the slide\'s own sentence; its numbers were checked against the values'
                     + (' (REVIEW: ' + '; '.join(F.claim_review).replace('--', '-') + ')' if F.claim_review else ''))
    facts.append(f'  - Axis 0 to {num(F.amax)} {F.unit}, ticks every {num(F.step)}: drawing scale, not data. -->')

    css = [f'''.anim-{N}{{
  --anim-bg:       var(--anim-theme-bg,       #0F1E27);
  --anim-panel:    var(--anim-theme-panel,    #0D1820);
  --anim-line:     var(--anim-theme-line,     #56707F);
  --anim-fg:       var(--anim-theme-fg,       #E6EDF0);
  --anim-muted:    var(--anim-theme-muted,    #93A7B2);
  --anim-accent:   var(--anim-theme-accent,   #34D1BF);
  --anim-accent-2: var(--anim-theme-accent-2, #FF8A3D);
  --anim-ok:       var(--anim-theme-ok,       #8ED7AD);
  --anim-warn:     var(--anim-theme-warn,     #FFD15C);
  --anim-danger:   var(--anim-theme-danger,   #FF6B6B);
  --anim-font:     var(--anim-theme-font,     "Avenir Next", "Segoe UI Variable Display", "Segoe UI", "Helvetica Neue", system-ui, sans-serif);
  --anim-mono:     var(--anim-theme-mono,     ui-monospace, "SF Mono", Menlo, Consolas, monospace);
  display:block;width:100%;height:100%
}}
.anim-{N} svg{{display:block;width:100%;height:100%;max-width:none}}
{P}t{{font-family:var(--anim-font);fill:var(--anim-fg)}}
{P}row{{font-size:{fs['row']}px;font-weight:600}}
{P}lbl{{font-size:{fs['lbl']}px;font-weight:600}}
{P}sub{{font-family:var(--anim-font);font-size:{fs['sub']}px;font-weight:400;fill:var(--anim-muted)}}
{P}note{{font-size:{fs['note']}px;font-weight:400}}
{P}num{{font-family:var(--anim-mono);font-size:{fs['sub']}px;font-weight:400;fill:var(--anim-muted);font-variant-numeric:tabular-nums}}
{P}val{{font-family:var(--anim-mono);font-size:{fs['lbl']}px;font-weight:400;fill:var(--anim-fg);font-variant-numeric:tabular-nums}}
{P}hero{{font-family:var(--anim-font);font-size:{fs['hero']}px;font-weight:500;letter-spacing:-0.02em;fill:var(--anim-accent);font-variant-numeric:tabular-nums}}
{P}herolbl{{font-size:{fs['row']}px;font-weight:500}}
{P}glow{{fill:var(--anim-accent);opacity:.3;filter:blur(8px)}}
{P}axis{{fill:none;stroke:var(--anim-line);stroke-width:2;stroke-linecap:round}}
{P}grid{{fill:none;stroke:var(--anim-line);stroke-width:1.5;stroke-dasharray:2 8;stroke-linecap:round}}
{P}start{{fill:none;stroke:var(--anim-muted);stroke-width:2;stroke-linecap:round}}
{P}band{{fill:color-mix(in srgb,var(--anim-fg) 10%,transparent);stroke:none}}
{P}edge{{fill:none;stroke:var(--anim-fg);stroke-width:2;stroke-linecap:butt}}
{P}div{{fill:none;stroke:var(--anim-fg);stroke-width:2;stroke-linecap:round}}
{P}end{{fill:none;stroke:var(--anim-fg);stroke-width:2;stroke-linecap:round}}
{P}guide{{fill:none;stroke:var(--anim-muted);stroke-width:1.5;stroke-dasharray:6 7;stroke-linecap:round}}
{P}brk{{fill:none;stroke:var(--anim-accent);stroke-width:2;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:100 120;stroke-dashoffset:0}}
{P}tag{{fill:none;stroke:var(--anim-line);stroke-width:1.5}}
/* every bar scales about the start line (transform-box view-box, px origin) */
{P}bar{{transform-box:view-box;transform-origin:{x0:.1f}px 0px}}''']

    dy = F.dy
    g_open = f'<g transform="translate(0 {dy:.1f})">' if dy else None
    if g_open:
        body.append(g_open)

    # ---- scene: notes, tag, calendar, row labels
    sc = [f'<g class="{N}-scene">']
    for i, n in enumerate(F.notes):
        sc.append(f'  <text class="{N}-sub" x="{PAD}" y="{38 + 26 * i}">{e(n)}</text>')
    if F.status == 'illustrative':
        tgw = tw('illustrative', fs['sub']) + 36
        sc.append(f'  <rect class="{N}-tag" x="{W - PAD - tgw:.1f}" y="20" width="{tgw:.1f}" height="36" rx="6"/>')
        sc.append(f'  <text class="{N}-sub" x="{W - PAD - tgw / 2:.1f}" y="44" text-anchor="middle">illustrative</text>')
    ticks = [F.step * i for i in range(F.nt + 1)]
    grid = ' '.join(filter(None, (cut(X(t), F.top, ya, F.boxes) for t in ticks[1:])))
    if grid:
        sc.append(f'  <path class="{N}-grid" d="{grid}"/>')
    sc.append(f'  <path class="{N}-axis" d="{" ".join(f"M{X(t):.1f} {ya:.1f} V{ya + 10:.1f}" for t in ticks)}"/>')
    for t in ticks:
        sc.append(f'  <text class="{N}-num" x="{X(t):.1f}" y="{ya + 36:.1f}" text-anchor="middle">{num(t)}</text>')
    sc.append(f'  <text class="{N}-sub" x="{X(F.amax) + 30:.1f}" y="{ya + 36:.1f}">{e(LONG.get(F.unit, F.unit))}</text>')
    if F.start:
        sc.append(f'  <text class="{N}-t {N}-lbl" x="{x0:.1f}" y="{F.top - 12:.1f}" text-anchor="middle">{e(F.start)}</text>')
    for x in B:
        for j, l in enumerate(x.lab):
            sc.append(f'  <text class="{N}-t {N}-row" x="{x0 - 24:.1f}" y="{x.lab_y + 34 * j:.1f}" text-anchor="end">{e(l)}</text>')
    sc.append('</g>')
    body += sc
    kf.append(f'@keyframes {N}-scene{{0%{{opacity:0;animation-timing-function:{ENTER}}}{pc(0.35, F)}{{opacity:1}}100%{{opacity:1}}}}')
    kf.append(f'@keyframes {N}-draw{{0%{{stroke-dashoffset:101;animation-timing-function:{ENTER}}}{pc(0.4, F)}{{stroke-dashoffset:0}}100%{{stroke-dashoffset:0}}}}')
    animate('scene')
    run.append(f'.visible .anim-{N} .{N}-drawon{{stroke-dasharray:101 101;animation:{N}-draw {F.end}s linear 1 both}}')
    body.append(f'<path class="{N}-axis {N}-drawon" pathLength="100" d="M{x0:.1f} {ya:.1f} H{X(F.amax):.1f}"/>')
    body.append(f'<path class="{N}-start {N}-drawon" pathLength="100" d="M{x0:.1f} {ya:.1f} V{F.top:.1f}"/>')

    # ---- the race
    for i, x in enumerate(B):
        xe, y = X(x.v), x.y
        body.append(f'<!-- {e(x.label)}: 0 to {num(x.v)} {F.unit}, {F.T0}-{x.t1:.3f} s -->')
        body.append(f'<g class="{N}-bar {N}-b{i}">')
        body.append(f'  <rect class="{N}-band" x="{x0:.1f}" y="{y:.1f}" width="{xe - x0:.2f}" height="{BH}"/>')
        body.append(f'  <path class="{N}-edge" d="M{x0:.1f} {y:.1f} H{xe:.2f} M{x0:.1f} {y + BH:.1f} H{xe:.2f}"/>')
        body.append('</g>')
        kf.append(f'@keyframes {N}-b{i}{{0%{{transform:scaleX(0)}}{pc(F.T0, F)}{{transform:scaleX(0);animation-timing-function:linear}}'
                  f'{pc(x.t1, F)}{{transform:scaleX(1)}}100%{{transform:scaleX(1)}}}}')
        animate(f'b{i}')
        under = x.stage_mode == 'under'
        for j, s in enumerate(x.stages):
            if j:
                xd = X(s.a)
                body.append(f'<path class="{N}-div {N}-d{i}-{j}" d="M{xd:.1f} {y + 2:.1f} V{y + BH + (26 if under else -2):.1f}"/>')
                kf.append(fade(f'{N}-d{i}-{j}', s.t, 0.15, F))
                animate(f'd{i}-{j}')
            if under:
                tx = X(s.a) + 12
                last_stage = j == len(x.stages) - 1
                t_in = (x.stages[j + 1].t if not last_stage else x.t1) + 0.08
                body.append(f'<g class="{N}-s{i}-{j}">')
                sp_ = ''.join(f'<tspan x="{tx:.1f}" dy="28">{e(l)}</tspan>' for l in s.lines[1:])
                body.append(f'  <text class="{N}-t {N}-lbl" x="{tx:.1f}" y="{y + BH + 50:.1f}">{e(s.lines[0])}{sp_}</text>')
                body.append(f'  <text class="{N}-num" x="{tx:.1f}" y="{y + BH + 76 + 28 * (len(s.lines) - 1):.1f}">{e(s.shown)}</text>')
                body.append('</g>')
                kf.append(fade(f'{N}-s{i}-{j}', t_in, 0.35, F, rise=10))
                animate(f's{i}-{j}')
        focal = ' data-anim-focal' if F.kind == 'none' and x is F.long else ''
        body.append(f'<g class="{N}-e{i}"{focal}>')
        body.append(f'  <path class="{N}-end" d="M{xe:.1f} {y - 10:.1f} V{y + BH + 10:.1f}"/>')
        if x.end:
            body.append(f'  <text class="{N}-t {N}-lbl" x="{xe + 20:.1f}" y="{y + 26:.1f}">{e(x.end)}</text>')
            body.append(f'  <text class="{N}-num" x="{xe + 20:.1f}" y="{y + 52:.1f}">{e(x.shown)}</text>')
        else:
            body.append(f'  <text class="{N}-val" x="{xe + 20:.1f}" y="{y + 37:.1f}">{e(x.shown)}</text>')
        body.append('</g>')
        kf.append(fade(f'{N}-e{i}', x.t1 + 0.08, 0.35, F, rise=10))
        animate(f'e{i}')

    # ---- the answer
    ta = F.ta
    if F.kind != 'none':
        xs, xl, yb = X(F.short.v), X(F.long.v), F.yb
        guides = ' '.join(filter(None, [cut(xs, F.short.y + BH + 16, yb - 18, F.boxes) if yb - 18 - (F.short.y + BH + 16) > 10 else '',
                                        cut(xl, F.long.y + BH + 16, yb - 18, F.boxes) if yb - 18 - (F.long.y + BH + 16) > 10 else '']))
        if guides:
            body.append(f'<g class="{N}-guide-g"><path class="{N}-guide" d="{guides}"/></g>')
            kf.append(fade(f'{N}-guide', ta, 0.25, F))
            animate('guide-g', 'guide')
        body.append('<g data-anim-focal>')
        body.append(f'  <path class="{N}-brk" pathLength="100" d="M{xs:.1f} {yb - 12:.1f} V{yb:.1f} H{xl:.1f} V{yb - 12:.1f}"/>')
        body.append(f'  <g class="{N}-hg"><text class="{N}-hero {N}-glow" x="{F.hx:.1f}" y="{F.yh:.1f}" text-anchor="end">{e(F.hero)}</text></g>')
        body.append(f'  <g class="{N}-ans-g">')
        body.append(f'    <text class="{N}-hero" x="{F.hx:.1f}" y="{F.yh:.1f}" text-anchor="end">{e(F.hero)}</text>')
        body.append(f'    <text class="{N}-t {N}-herolbl" x="{F.hx + 14:.1f}" y="{F.yh:.1f}">{e(F.hero_words)}</text>')
        body.append('  </g>')
        body.append('</g>')
        kf.append(f'@keyframes {N}-brk{{0%{{stroke-dashoffset:101}}{pc(ta + 0.2, F)}{{stroke-dashoffset:101;animation-timing-function:{ENTER}}}'
                  f'{pc(ta + 0.75, F)}{{stroke-dashoffset:0}}100%{{stroke-dashoffset:0}}}}')
        animate('brk')
        kf.append(fade(f'{N}-ans', ta + 0.6, 0.4, F, rise=12))
        animate('ans-g', 'ans')
        kf.append(fade(f'{N}-glow', ta + 0.7, 0.4, F))
        animate('hg', 'glow')

    # ---- captions: the slide's own words, cross-faded; the last one stays
    if F.yc:
        seq = []
        if F.opening:
            seq.append((F.opening, 0.05))
        if F.mid:
            seq.append((F.mid, min(x.t1 for x in B if x.stage_mode == 'caption') + 0.25))
        if F.claim:
            seq.append((F.claim, ta + 0.1))
        hidden = []
        for i, (text, t_in) in enumerate(seq):
            out = seq[i + 1][1] - 0.1 if i + 1 < len(seq) else None
            if out is not None and out - t_in < 0.6:
                out = t_in + 0.6
            body.append(f'<text class="{N}-t {N}-note {N}-n{i}" x="{W / 2:.1f}" y="{F.yc:.1f}" text-anchor="middle">{e(text)}</text>')
            kf.append(fade(f'{N}-n{i}', t_in, 0.35, F, out=out))
            animate(f'n{i}')
            if out is not None:
                hidden.append(f'{P}n{i}')
        if hidden:
            css.append('/* resting frame = the end: earlier captions are gone */\n' + ','.join(hidden) + '{opacity:0}')
    if g_open:
        body.append('</g>')

    said = '; '.join(f'{x.label} {x.shown}' for x in B)
    if F.kind == 'difference':
        ans = f' A bracket marks {F.long.label} as {F.hero} {F.hero_words} than {F.short.label}.'
    elif F.kind == 'ratio':
        ans = f' A bracket marks {F.long.label} as {F.hero} {F.hero_words.replace(", rounded", "")} as {F.short.label}.'
    else:
        ans = ''
    aria = (f'{"Illustrative durations" if F.status == "illustrative" else "Durations"} on one {unit_word(F.unit, 1)} axis: '
            f'{said}. The bars start together and grow at the same rate; each stops at its own length.{ans}'
            + (f' {F.claim}' if F.claim else ''))
    out = facts + ['<style>'] + css + [f'/* ---- motion ({F.end} s once pass), only when the slide is visible. Enter {ENTER}, linear for the race */']
    out += kf + [''] + run + ['', f'@media (prefers-reduced-motion: reduce) {{ .anim-{N} * {{ animation: none !important; }} }}', '</style>']
    out.append(f'<div class="anim anim-{N}" data-anim="{N}" data-anim-cycle="{F.end}" data-anim-control="once" '
               f'data-anim-phases="{",".join(str(m) for m in F.marks)}" data-anim-verb="race">')
    out.append(f'<svg viewBox="0 0 {W} {H}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" role="img" '
               f'aria-label="{escape(aria, quote=True)}">')
    out += body + ['</svg>', '</div>']
    return '\n'.join(out) + '\n'


def summary(F):
    lines = [f'durations: {len(F.bars)} bars on one {F.unit} axis (0 to {num(F.amax)}), viewBox {F.W}x{F.H}, pass {F.end} s']
    for x in F.bars:
        lines.append(f'  {x.label}: {x.shown} -> {F.scale * x.v:.1f} px, stops at {x.t1:.2f} s')
    if F.kind != 'none':
        lines.append(f'  takeaway ({F.kind}, {F.long.label} against {F.short.label}): {F.hero} {F.hero_words}')
    if F.claim and not F.claim_review:
        lines.append('  claim: every number in the sentence follows from the values')
    for r in getattr(F, 'claim_review', []):
        lines.append(f'  REVIEW claim: {r}. Read "{F.claim}" against the figure, reword it if it is wrong, '
                     'and name this line in the hand-over')
    short = min(F.scale * x.v for x in F.bars)
    if short < 12:
        lines.append(f'  note: the shortest bar is {short:.1f} px, drawn to scale. That gap is the point; '
                     'do not stretch it or break the axis')
    return lines


def build(sp, output, rendered=None, stage=1920, check=True, spec_name='spec.yaml'):
    """Plan, render and check. The destination is replaced only by a build that passes: a spec
    error or a failing check leaves the file that was there (or no file) and exits non-zero."""
    F = plan(sp, rendered, stage)
    html = render(F, spec_name)
    out_dir = os.path.dirname(os.path.abspath(output))
    os.makedirs(out_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + os.path.basename(output) + '.', suffix='.html', dir=out_dir)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write(html)
        print('\n'.join(summary(F)))
        code = 0
        if check:
            checker = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'check_fragment.py')
            r = subprocess.run([sys.executable, checker, tmp, '--name', F.name, '--rendered-width',
                                f'{rendered or F.W:g}', '--stage-width', f'{stage:g}'], capture_output=True, text=True)
            print(r.stdout.replace(tmp, output), end='')
            code = r.returncode
        if code:
            print(f'not written: {output} ' + ('is unchanged (the last build that passed)' if os.path.exists(output)
                                               else 'was not created') + '; --no-check writes a failing build for inspection')
            return code
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(tmp, 0o666 & ~umask)
        os.replace(tmp, output)
        tmp = None
        print(f'wrote {output}')
        return 0
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def main():
    ap = argparse.ArgumentParser(description='Build a duration race fragment from a spec.')
    ap.add_argument('spec')
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--rendered-width', type=float)
    ap.add_argument('--stage-width', type=float, default=1920)
    ap.add_argument('--no-check', action='store_true')
    a = ap.parse_args()
    try:
        code = build(load(a.spec), a.output, a.rendered_width, a.stage_width, not a.no_check, os.path.basename(a.spec))
    except SpecError as err:
        sys.exit(f'race_figure: {err}')
    if code:
        sys.exit('race_figure: the output fails check_fragment.py (see above)')


if __name__ == '__main__':
    main()
