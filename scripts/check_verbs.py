#!/usr/bin/env python3
"""Motion variety across a deck: does one verb, or the travelling marker, carry most slides?

Every fragment names its main motion in data-anim-verb (references/motion-verbs.md). A deck
where most fragments share one verb has usually drawn the layout of its text, not its ideas.
This check counts the verbs of a deck's fragments and asks for a reason on each repeat.

Usage:
  check_verbs.py DECK.html [--triage anim/triage.md]
  check_verbs.py --dir anim/ [--triage anim/triage.md]     every anim/<name>/<name>.html
  check_verbs.py --pool pool/index.yaml                    the pool: verb per entry, marker share

Rules (the share is of animated fragments; a rule needs at least three fragments to apply):
  verb         FAIL  a fragment without data-anim-verb, or with a verb outside the vocabulary
  repeat       FAIL  one verb on more than a third of the fragments (and at least three) where
                     a repeat has no reason; the reason is written in the triage row's Verb
                     cell after a colon: "reveal: the source states order only",
                     "travel: the parcel, depot to doorstep"
  marker       FAIL  a travelling marker (offset-path) under a verb other than travel or cycle;
               FAIL  markers (offset-path, or the verb travel) on more than a third of the fragments (and at least three) where a
                     travel row does not name its traveller in the triage
  neighbours   WARN  the same verb on two animated slides in a row (deck order)
  triage       WARN  a fragment whose verb differs from its triage row

--pool applies `verb` and the one-third `marker` limit to pool/index.yaml (entries need `verb:`;
an entry whose moves list packet-hop counts as a marker) and prints the distribution.

Exit code 1 on any FAIL, 0 otherwise. No dependencies.
"""
import argparse
import math
import os
import re
import sys
from collections import Counter, OrderedDict

VERBS = ['grow', 'count', 'accumulate', 'thin', 'race', 'split', 'merge', 'sort', 'stack', 'nest',
         'transform', 'wipe', 'switch', 'balance', 'drive', 'zoom', 'open', 'travel', 'trace', 'cycle',
         'reveal']
MARKER_VERBS = ('travel', 'cycle')
VAGUE_TRAVELLERS = {'', 'dot', 'a dot', 'packet', 'a packet', 'token', 'a token', 'marker', 'a marker', 'it'}

WRAP_RE = re.compile(r'<(?:div|figure|section|span)\b[^>]*\bclass="[^"]*\banim-([a-z0-9][a-z0-9-]*)\b[^"]*"[^>]*>', re.I)
VERB_ATTR_RE = re.compile(r'\bdata-anim-verb="([^"]*)"', re.I)


class Report:
    def __init__(self):
        self.fails = 0
        self.warns = 0

    def ok(self, rule, msg):
        print(f'ok    {rule}: {msg}')

    def warn(self, rule, msg):
        self.warns += 1
        print(f'WARN  {rule}: {msg}')

    def fail(self, rule, msg):
        self.fails += 1
        print(f'FAIL  {rule}: {msg}')


def fragments_in_html(text):
    """Fragments in document order: name, verb (None when the attribute is missing), has a marker."""
    out = OrderedDict()
    for m in WRAP_RE.finditer(text):
        tag, name = m.group(0), m.group(1)
        if name in out or not re.search(r'\bclass="[^"]*\banim\b', tag):
            continue
        v = VERB_ATTR_RE.search(tag)
        vs = v.group(1).strip().lower().split() if v else []
        out[name] = {'name': name, 'verb': (vs[0] if vs else '') if v else None, 'support': vs[1:], 'marker': False}
    # a marker is an offset-path declared in a rule of that fragment
    for rule in re.finditer(r'([^{}]*)\{([^{}]*)\}', text):
        if 'offset-path' not in rule.group(2):
            continue
        for name in out:
            if re.search(r'\.anim-' + re.escape(name) + r'(?![a-z0-9-])', rule.group(1)):
                out[name]['marker'] = True
    return list(out.values())


def fragments_in_dir(root):
    frags = []
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name, name + '.html')
        if os.path.isfile(path):
            found = fragments_in_html(open(path, encoding='utf-8').read())
            hit = [f for f in found if f['name'] == name] or found[:1]
            if hit:
                frags.append(hit[0])
    return frags


def read_triage(path):
    """Rows of the triage table that are illustrated: list of dicts with verb, reason, slide, name."""
    rows, header = [], None
    for line in open(path, encoding='utf-8'):
        if not line.lstrip().startswith('|'):
            header = None if not line.strip() else header
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if all(re.fullmatch(r':?-+:?', c) for c in cells):
            continue
        if 'verb' not in header:
            continue
        row = dict(zip(header, cells))
        cell = row.get('verb', '').strip().strip('`')
        if cell in ('', '-'):
            continue
        verb, _, reason = cell.partition(':')
        rows.append({'verb': verb.strip().strip('`').lower(), 'reason': reason.strip(),
                     'slide': row.get('slide', '?'), 'text': ' '.join(cells).lower()})
    return rows


def match_row(frag, rows, used):
    """The triage row of a fragment: one that mentions its name, else the next unused row in order."""
    for i, r in enumerate(rows):
        if i not in used and re.search(r'(?<![a-z0-9-])' + re.escape(frag['name']) + r'(?![a-z0-9-])', r['text']):
            used.add(i)
            return r
    for i, r in enumerate(rows):
        if i not in used:
            used.add(i)
            return r
    return None


def check_deck(frags, rows, R, source):
    n = len(frags)
    if n == 0:
        R.warn('verb', f'no fragments found in {source}')
        return
    used = set()
    for f in frags:
        f['row'] = match_row(f, rows, used) if rows is not None else None

    bad = False
    for f in frags:
        if f['verb'] is None:
            R.fail('verb', f"{f['name']}: no data-anim-verb on the wrapper; name the main motion "
                           f"(references/motion-verbs.md)")
            bad = True
        elif f['verb'] not in VERBS:
            R.fail('verb', f"{f['name']}: data-anim-verb=\"{f['verb']}\" is not a verb; one of: {', '.join(VERBS)}")
            bad = True
        elif f['row'] and f['row']['verb'] != f['verb']:
            R.warn('triage', f"{f['name']}: fragment says {f['verb']}, triage row (slide {f['row']['slide']}) "
                             f"says {f['row']['verb']}")
    if not bad:
        R.ok('verb', f'{n} fragment(s), each with a verb')

    counts = Counter(f['verb'] for f in frags if f['verb'] in VERBS)
    print('      verbs: ' + ', '.join(f'{v} {c}' for v, c in counts.most_common()))
    limit = n / 3.0
    repeated = [v for v, c in counts.items() if c >= 3 and c > limit]
    if not repeated:
        R.ok('repeat', f'no verb on more than a third of {n} fragment(s)')
    for v in repeated:
        mine = [f for f in frags if f['verb'] == v]
        missing = [f['name'] for f in mine if not (f['row'] and f['row']['reason'])]
        if rows is None:
            R.fail('repeat', f"{v} is the verb of {len(mine)} of {n} fragments (more than a third); pass "
                             f"--triage anim/triage.md with a reason per repeat in the Verb cell "
                             f"(\"{v}: <what the source says>\")")
        elif missing:
            R.fail('repeat', f"{v} is the verb of {len(mine)} of {n} fragments (more than a third) and "
                             f"{len(missing)} carry no reason in their triage row: {', '.join(missing)}. Re-read "
                             f"those slides for what else they say, or write the reason after the verb "
                             f"(\"{v}: <what the source says>\")")
        else:
            R.ok('repeat', f'{v} on {len(mine)} of {n} fragments, each with a reason in the triage')

    markers = [f for f in frags if f['marker'] or f['verb'] == 'travel']
    stray = [f['name'] for f in markers if f['marker'] and f['verb'] in VERBS
             and not (set([f['verb']] + f.get('support', [])) & set(MARKER_VERBS))]
    if stray:
        R.fail('marker', f"travelling marker (offset-path) under a verb other than travel or cycle: "
                         f"{', '.join(stray)}; remove the marker or the verb is wrong")
    if len(markers) >= 3 and len(markers) > limit:
        unnamed = [f['name'] for f in markers if f['verb'] == 'travel'
                   and not (f['row'] and f['row']['reason'].lower() not in VAGUE_TRAVELLERS)]
        if rows is None or unnamed:
            who = ', '.join(unnamed) if unnamed else 'no triage given'
            R.fail('marker', f"{len(markers)} of {n} fragments have a travelling marker (more than a third); each "
                             f"travel row names its traveller in the triage (\"travel: the parcel\"): {who}")
        else:
            R.ok('marker', f'{len(markers)} of {n} fragments have a marker, each traveller named')
    elif not stray:
        R.ok('marker', f'{len(markers)} of {n} fragment(s) have a travelling marker')

    pairs = [f"{a['name']} + {b['name']} ({a['verb']})" for a, b in zip(frags, frags[1:])
             if a['verb'] == b['verb'] and a['verb'] in VERBS]
    if pairs:
        R.warn('neighbours', 'same verb on fragments in a row: ' + '; '.join(pairs))


def read_pool(path):
    entries, cur = [], None
    for line in open(path, encoding='utf-8'):
        m = re.match(r'-\s+name:\s*(\S+)', line)
        if m:
            cur = {'name': m.group(1), 'verb': None, 'moves': []}
            entries.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r'\s+verb:\s*([a-z-]+)', line)
        if m:
            cur['verb'] = m.group(1)
        m = re.match(r'\s+moves:\s*\[(.*)\]', line)
        if m:
            cur['moves'] = [x.strip() for x in m.group(1).split(',') if x.strip()]
    return entries


def check_pool(path, R):
    entries = read_pool(path)
    n = len(entries)
    bad = [e['name'] for e in entries if e['verb'] not in VERBS]
    if bad:
        R.fail('verb', f"{len(bad)} pool entr{'y' if len(bad) == 1 else 'ies'} without a verb from the "
                       f"vocabulary: {', '.join(bad)}")
    else:
        R.ok('verb', f'{n} entries, each with a verb')
    counts = Counter(e['verb'] for e in entries if e['verb'] in VERBS)
    print('      verbs: ' + ', '.join(f'{v} {c}' for v, c in counts.most_common()))
    absent = [v for v in VERBS if v not in counts and v != 'count']  # count is always a supporting verb
    if absent:
        R.warn('coverage', f"no pool entry for: {', '.join(absent)}")
    markers = [e['name'] for e in entries if 'packet-hop' in e['moves'] or e['verb'] == 'travel']
    cap = math.floor(n / 3)
    if len(markers) > cap:
        R.fail('marker', f'{len(markers)} of {n} pool entries use a travelling marker; at most a third ({cap}): '
                         f"{', '.join(markers)}")
    else:
        R.ok('marker', f'{len(markers)} of {n} pool entries use a travelling marker (at most {cap})')
    stray = [e['name'] for e in entries if 'packet-hop' in e['moves'] and e['verb'] not in MARKER_VERBS]
    if stray:
        R.fail('marker', f"packet-hop listed under a verb other than travel or cycle: {', '.join(stray)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split('\n\n', 2)[2])
    ap.add_argument('deck', nargs='?', help='the deck HTML with its integrated fragments')
    ap.add_argument('--dir', help='a work folder of fragments: <dir>/<name>/<name>.html')
    ap.add_argument('--triage', help='anim/triage.md, for the reasons of repeated verbs')
    ap.add_argument('--pool', help='pool/index.yaml: check the pool instead of a deck')
    a = ap.parse_args()
    if sum(bool(x) for x in (a.deck, a.dir, a.pool)) != 1:
        ap.error('give exactly one of DECK.html, --dir or --pool')
    R = Report()
    if a.pool:
        check_pool(a.pool, R)
    else:
        rows = read_triage(a.triage) if a.triage else None
        if a.deck:
            frags = fragments_in_html(open(a.deck, encoding='utf-8').read())
            check_deck(frags, rows, R, a.deck)
        else:
            check_deck(fragments_in_dir(a.dir), rows, R, a.dir)
    print(f"{'FAIL' if R.fails else 'PASS'}: {R.fails} fail, {R.warns} warn")
    sys.exit(1 if R.fails else 0)


if __name__ == '__main__':
    main()
