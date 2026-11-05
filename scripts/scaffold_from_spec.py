#!/usr/bin/env python3
"""Scaffold an anim-slides fragment from a spec (references/spec-format.md).

Usage:
  scaffold_from_spec.py SPEC.yaml|SPEC.json -o OUT.html
        [--viewbox W H] [--rendered-width PX] [--min-text 18]
        [--control loop|step] [--no-check]

  --viewbox         override the spec's size (viewBox width and height)
  --rendered-width  CSS px the SVG is shown at (default: the viewBox width); font sizes are
                    raised so every text meets --min-text there; the self-check uses it too
  --min-text        minimum rendered text size in px (18 on a 1920 stage)
  --control         override the spec's control (loop | step)
  --no-check        do not run check_fragment.py on the output

The output is a skeleton that satisfies references/fragment-contract.md: a layout per archetype
(references/archetypes.md), phase timing from the spec, gated keyframes (loop) or a paused GSAP
timeline (step). Refine it by hand (see the scaffold comment at the top of the output), then run
render-phases.sh and look at every PNG.
Specs are YAML or JSON. PyYAML is used when installed; without it a built-in reader covers the
plain subset the examples use (block and flow collections, quoted and plain scalars, comments).
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
from html import escape

ARCHETYPES = ('pipeline', 'graph', 'timeline', 'states', 'compare', 'layers', 'chart')
DEFAULT_SIZE = {'pipeline': (1680, 440), 'timeline': (1680, 440), 'graph': (1680, 600),
                'compare': (1680, 600), 'chart': (1680, 600), 'states': (1200, 600),
                'layers': (1200, 600)}
NODE_KINDS = ('process', 'data', 'actor', 'decision', 'external', 'store', 'milestone')
EDGE_KINDS = ('flow', 'depends', 'data', 'event')
KEYS = {
    'top': {'name', 'archetype', 'title', 'size', 'control', 'cycle', 'nodes', 'edges', 'groups',
            'phases', 'series', 'events'},
    'node': {'id', 'label', 'sub', 'kind', 'group', 'at', 'side', 'layer'},
    'edge': {'from', 'to', 'label', 'kind'},
    'group': {'id', 'label'},
    'phase': {'t', 'label', 'show', 'active', 'flow', 'note'},
    'series': {'id', 'label', 'points'},
    'event': {'id', 'at', 'label'},
}
ID_RE = re.compile(r'[a-z][a-z0-9]*(-[a-z0-9]+)*')
# name: (CSS timing function, GSAP ease)
EASE = {'enter': ('cubic-bezier(0.16,1,0.3,1)', 'expo.out'),
        'exit': ('cubic-bezier(0.3,0,1,1)', 'power2.in'),
        'move': ('cubic-bezier(0.45,0,0.55,1)', 'power2.inOut'),
        'linear': ('linear', 'none')}
STEP = 1.2     # step mode: timeline seconds between phase labels
RESET = 0.4    # loop mode: the last seconds of the cycle fade back to the empty state


def die(msg):
    sys.exit(f'scaffold_from_spec: error: {msg}')


def warn(msg):
    print(f'scaffold_from_spec: warning: {msg}', file=sys.stderr)


def f1(v):
    return f'{v:.1f}'.rstrip('0').rstrip('.')


def pt(p):
    return f'{f1(p[0])},{f1(p[1])}'


# ============================================================================ spec
# ----------------------------------------------------------------------------- YAML subset
class MiniYAMLError(ValueError):
    pass


def mini_yaml(text):
    """Parse the YAML subset specs use, without PyYAML: block mappings and sequences by
    indentation, flow collections ([..], {..}), quoted and plain scalars, comments.
    Not supported (use PyYAML or JSON): anchors, tags, multi-line scalars, multiple documents."""

    def strip_comment(line):
        q = None
        for i, ch in enumerate(line):
            if q:
                if ch == q:
                    q = None
            elif ch in '"\'':
                q = ch
            elif ch == '#' and (i == 0 or line[i - 1] in ' \t'):
                return line[:i]
        return line

    lines = []
    for no, raw in enumerate(text.splitlines(), 1):
        if raw.startswith('---') or raw.startswith('...'):
            continue
        body = strip_comment(raw.replace('\t', '  ')).rstrip()
        if body.strip():
            lines.append((len(body) - len(body.lstrip(' ')), body.strip(), no))

    def scalar(tok):
        if tok in ('', '~', 'null', 'Null', 'NULL'):
            return None
        if tok in ('true', 'True', 'TRUE'):
            return True
        if tok in ('false', 'False', 'FALSE'):
            return False
        if re.fullmatch(r'[-+]?\d+', tok):
            return int(tok)
        if re.fullmatch(r'[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?', tok):
            return float(tok)
        return tok

    def flow_value(src, i, no):
        """Parse one value starting at src[i]; return (value, index after it)."""
        while i < len(src) and src[i] == ' ':
            i += 1
        if i >= len(src):
            raise MiniYAMLError(f'line {no}: unexpected end of value')
        ch = src[i]
        if ch == '[':
            out, i = [], i + 1
            while True:
                while i < len(src) and src[i] in ' ,':
                    i += 1
                if i >= len(src):
                    raise MiniYAMLError(f'line {no}: unclosed [')
                if src[i] == ']':
                    return out, i + 1
                v, i = flow_value(src, i, no)
                out.append(v)
        if ch == '{':
            out, i = {}, i + 1
            while True:
                while i < len(src) and src[i] in ' ,':
                    i += 1
                if i >= len(src):
                    raise MiniYAMLError(f'line {no}: unclosed {{')
                if src[i] == '}':
                    return out, i + 1
                k, i = flow_value(src, i, no)
                while i < len(src) and src[i] == ' ':
                    i += 1
                if i >= len(src) or src[i] != ':':
                    raise MiniYAMLError(f'line {no}: expected ":" after key {k!r} in {{...}}')
                i += 1
                while i < len(src) and src[i] == ' ':
                    i += 1
                if i < len(src) and src[i] in ',}':
                    out[k] = None
                else:
                    out[k], i = flow_value(src, i, no)
        if ch in '"\'':
            j, buf = i + 1, []
            while j < len(src):
                c = src[j]
                if ch == '"' and c == '\\' and j + 1 < len(src):
                    buf.append({'n': '\n', 't': '\t'}.get(src[j + 1], src[j + 1])); j += 2; continue
                if ch == "'" and c == "'" and j + 1 < len(src) and src[j + 1] == "'":
                    buf.append("'"); j += 2; continue
                if c == ch:
                    return ''.join(buf), j + 1
                buf.append(c); j += 1
            raise MiniYAMLError(f'line {no}: unclosed quote')
        j = i                                    # plain scalar: up to , ] } or ": " at depth 0
        while j < len(src) and src[j] not in ',]}' and not (src[j] == ':' and (j + 1 == len(src) or src[j + 1] == ' ')):
            j += 1
        return scalar(src[i:j].strip()), j

    def value_from(src, no):
        """A complete scalar or flow collection occupying the rest of a line."""
        src = src.strip()
        if src and src[0] in '[{"\'':
            v, i = flow_value(src, 0, no)
            if src[i:].strip():
                raise MiniYAMLError(f'line {no}: trailing text after value: {src[i:].strip()!r}')
            return v
        if src.startswith(('&', '*', '!', '|', '>')):
            raise MiniYAMLError(f'line {no}: anchors, tags and block scalars are not supported; '
                                'install PyYAML or use JSON')
        return scalar(src)

    def split_key(content, no):
        """'key: rest' -> (key, rest) honouring quotes; None when the line is not a mapping entry."""
        q = None
        for i, ch in enumerate(content):
            if q:
                if ch == q:
                    q = None
            elif ch in '"\'' and i == 0:
                q = ch
            elif ch in '[{':
                return None
            elif ch == ':' and (i + 1 == len(content) or content[i + 1] == ' '):
                key = content[:i].strip()
                if key[:1] in '"\'':
                    key = key[1:-1]
                return key, content[i + 1:].strip()
        return None

    pos = [0]

    def parse_block(indent):
        ind, content, no = lines[pos[0]]
        if content == '-' or content.startswith('- '):
            return parse_seq(indent)
        return parse_map(indent)

    def nested(indent, no):
        """Value of an entry whose rest-of-line is empty: the block on the following lines."""
        if pos[0] < len(lines) and lines[pos[0]][0] > indent:
            return parse_block(lines[pos[0]][0])
        if pos[0] < len(lines) and lines[pos[0]][0] == indent and lines[pos[0]][1].startswith('-'):
            return parse_seq(indent)           # "key:\n- item" at the same indent
        return None

    def parse_map(indent):
        out = {}
        while pos[0] < len(lines):
            ind, content, no = lines[pos[0]]
            if ind < indent:
                break
            if ind > indent:
                raise MiniYAMLError(f'line {no}: unexpected indentation')
            if content.startswith('- ') or content == '-':
                break
            kv = split_key(content, no)
            if not kv:
                raise MiniYAMLError(f'line {no}: expected "key: value", got {content!r}')
            key, rest = kv
            if key in out:
                raise MiniYAMLError(f'line {no}: duplicate key {key!r}')
            pos[0] += 1
            out[key] = value_from(rest, no) if rest else nested(indent, no)
        return out

    def parse_seq(indent):
        out = []
        while pos[0] < len(lines):
            ind, content, no = lines[pos[0]]
            if ind < indent or not (content == '-' or content.startswith('- ')):
                break
            if ind > indent:
                raise MiniYAMLError(f'line {no}: unexpected indentation')
            rest = content[1:].strip()
            if not rest:
                pos[0] += 1
                out.append(nested(indent, no))
            elif split_key(rest, no) and rest[0] not in '[{"\'':
                # "- key: value" starts a block mapping indented past the dash
                sub = indent + 1 + (len(content) - 1 - len(content[1:].lstrip(' ')))
                lines[pos[0]] = (sub, rest, no)
                out.append(parse_map(sub))
            else:
                pos[0] += 1
                out.append(value_from(rest, no))
        return out

    if not lines:
        return None
    data = parse_block(lines[0][0])
    if pos[0] < len(lines):
        raise MiniYAMLError(f'line {lines[pos[0]][2]}: unexpected content {lines[pos[0]][1]!r}')
    return data


def load_spec(path):
    try:
        text = open(path, encoding='utf-8').read()
    except OSError as e:
        die(f'cannot read {path}: {e.strerror}')
    if path.endswith('.json') or text.lstrip().startswith('{'):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            die(f'{path}: invalid JSON: {e}')
    else:
        try:
            import yaml
        except ImportError:
            yaml = None
        if yaml:
            try:
                data = yaml.safe_load(text)
            except yaml.YAMLError as e:
                die(f'{path}: invalid YAML: {e}')
        else:                                   # stdlib fallback for the usual spec subset
            try:
                data = mini_yaml(text)
            except MiniYAMLError as e:
                die(f'{path}: {e} (the built-in reader covers plain specs; '
                    'pip install pyyaml for full YAML, or pass JSON)')
    if not isinstance(data, dict):
        die(f'{path}: the spec must be a mapping')
    return data


class Spec:
    pass


def validate(sp, args):
    err = []

    def need(cond, msg):
        if not cond:
            err.append(msg)
        return cond

    def check_keys(d, kind, where):
        if not isinstance(d, dict):
            err.append(f'{where} must be a mapping')
            return False
        extra = set(d) - KEYS[kind]
        need(not extra, f'{where}: unknown key(s) {", ".join(sorted(extra))}')
        return True

    def ok_id(v, where):
        return need(isinstance(v, str) and ID_RE.fullmatch(v) and len(v) <= 24,
                    f'{where}: id {v!r} must be kebab-case, at most 24 chars')

    def hint(text, n, where):
        if text and len(str(text)) > n:
            warn(f'{where} is {len(str(text))} chars (hint: max ~{n})')

    S = Spec()
    S.name = sp.get('name')
    need(isinstance(S.name, str) and ID_RE.fullmatch(S.name) and 2 <= len(S.name) <= 24,
         f'name {S.name!r} must be kebab-case, 2-24 chars')
    S.arch = sp.get('archetype')
    need(S.arch in ARCHETYPES, f'archetype {S.arch!r} must be one of {", ".join(ARCHETYPES)}')
    if err:                      # everything below depends on name and archetype
        die('; '.join(err))
    check_keys(sp, 'top', 'spec')
    spec_control = sp.get('control', 'loop')
    S.control = args.control or spec_control
    need(S.control in ('loop', 'step'), f'control {S.control!r} must be loop or step')
    S.cycle = sp.get('cycle', 12)
    if S.control == 'loop':
        need(isinstance(S.cycle, (int, float)) and 8 <= S.cycle <= 15, 'cycle must be 8-15 s')
    size = args.viewbox or sp.get('size') or DEFAULT_SIZE[S.arch]
    need(isinstance(size, (list, tuple)) and len(size) == 2
         and all(isinstance(v, int) and v > 0 for v in size), 'size must be [W, H], positive integers')
    S.W, S.H = size if len(size) == 2 else (0, 0)
    S.title = str(sp['title']) if sp.get('title') else None
    hint(S.title, 48, 'title')

    S.nodes, S.groups, S.series, S.events = [], [], [], []
    for i, n in enumerate(sp.get('nodes') or []):
        w = f'nodes[{i}]'
        if not check_keys(n, 'node', w):
            continue
        n = dict(n)
        ok_id(n.get('id'), w)
        need(n.get('label') not in (None, ''), f'{w}: label is required')
        n['label'] = str(n.get('label', ''))
        n['sub'] = str(n['sub']) if n.get('sub') not in (None, '') else None
        n.setdefault('kind', 'process')
        need(n['kind'] in NODE_KINDS, f'{w}: kind {n["kind"]!r} unknown')
        for fld, arch in (('at', 'timeline'), ('side', 'compare'), ('layer', 'layers')):
            if S.arch == arch:
                need(fld in n, f'{w}: {fld} is required for {arch}')
            else:
                need(fld not in n, f'{w}: {fld} is only allowed in {arch}')
        if S.arch == 'compare':
            need(n.get('side') in ('left', 'right'), f'{w}: side must be left or right')
        if S.arch == 'layers':
            need(isinstance(n.get('layer'), int) and n.get('layer', -1) >= 0, f'{w}: layer must be an integer >= 0')
        hint(n['label'], 24, f'{w}.label')
        hint(n['sub'], 28, f'{w}.sub')
        S.nodes.append(n)
    need(S.nodes or S.arch == 'chart', 'nodes: at least one node is required')
    need(len(S.nodes) <= 20, 'nodes: at most 20')
    if len(S.nodes) > 12:
        warn(f'{len(S.nodes)} nodes (more than 12 is hard to read; consider splitting)')
    if S.arch == 'layers':
        need(len({n.get('layer') for n in S.nodes}) <= 5, 'layers: at most 5 distinct layers')
    for i, g in enumerate(sp.get('groups') or []):
        if check_keys(g, 'group', f'groups[{i}]'):
            ok_id(g.get('id'), f'groups[{i}]')
            need(g.get('label'), f'groups[{i}]: label is required')
            S.groups.append(dict(g, label=str(g.get('label', ''))))
    need(len(S.groups) <= 4, 'groups: at most 4')
    if S.arch == 'chart':
        for i, s in enumerate(sp.get('series') or []):
            if not check_keys(s, 'series', f'series[{i}]'):
                continue
            ok_id(s.get('id'), f'series[{i}]')
            p = s.get('points') or []
            good = (2 <= len(p) <= 200 and all(isinstance(q, (list, tuple)) and len(q) == 2
                    and all(isinstance(v, (int, float)) for v in q) for q in p))
            if need(good, f'series[{i}]: points must be 2-200 [x, y] number pairs'):
                need(all(p[k][0] < p[k + 1][0] for k in range(len(p) - 1)),
                     f'series[{i}]: x must be strictly increasing')
            S.series.append(dict(s, label=str(s.get('label', s.get('id')))))
        need(1 <= len(S.series) <= 3, 'chart needs 1 to 3 series')
        xs = [q[0] for s in S.series for q in s.get('points') or [] if isinstance(q, (list, tuple))]
        for i, e in enumerate(sp.get('events') or []):
            if not check_keys(e, 'event', f'events[{i}]'):
                continue
            e = dict(e)
            e.setdefault('id', f'event-{i + 1}')
            ok_id(e['id'], f'events[{i}]')
            need(isinstance(e.get('at'), (int, float)) and xs and min(xs) <= e['at'] <= max(xs),
                 f'events[{i}]: at must be inside the x range')
            e['label'] = str(e.get('label', ''))
            hint(e['label'], 20, f'events[{i}].label')
            S.events.append(e)
        if S.nodes:
            warn('chart: nodes are not drawn by the chart scaffold')
            S.nodes = []
    else:
        need(not sp.get('series') and not sp.get('events'), 'series and events are only allowed in chart')

    ids = [x['id'] for x in S.nodes + S.groups + S.series + S.events]
    dup = {i for i in ids if ids.count(i) > 1}
    need(not dup, f'duplicate id(s): {", ".join(sorted(dup))}')
    S.node = {n['id']: n for n in S.nodes}
    S.group = {g['id']: g for g in S.groups}
    for n in S.nodes:
        if n.get('group') is not None:
            need(n['group'] in S.group, f'node {n["id"]}: group {n["group"]!r} not in groups')
    for g in S.groups:
        need(any(n.get('group') == g['id'] for n in S.nodes), f'group {g["id"]} has no members')

    raw_edges = sp.get('edges') or []
    if S.arch == 'pipeline' and not raw_edges:
        raw_edges = [{'from': a['id'], 'to': b['id']} for a, b in zip(S.nodes, S.nodes[1:])]
    S.edges = []
    for i, e in enumerate(raw_edges):
        if not check_keys(e, 'edge', f'edges[{i}]'):
            continue
        e = dict(e)
        need(e.get('from') in S.node and e.get('to') in S.node, f'edges[{i}]: from/to must be node ids')
        need(e.get('from') != e.get('to'), f'edges[{i}]: from == to')
        e.setdefault('kind', 'flow')
        need(e['kind'] in EDGE_KINDS, f'edges[{i}]: kind {e["kind"]!r} unknown')
        e['id'] = f'{e.get("from")}>{e.get("to")}'
        e['label'] = str(e['label']) if e.get('label') not in (None, '') else None
        hint(e['label'], 16, f'edges[{i}].label')
        need(e['id'] not in [x['id'] for x in S.edges], f'edges[{i}]: duplicate edge {e["id"]}')
        S.edges.append(e)
    S.edge = {e['id']: e for e in S.edges}
    rids = [f'{e["from"]}-{e["to"]}' for e in S.edges]
    need(len(set(rids)) == len(rids), 'two edges render to the same id <from>-<to>; rename a node')
    if len(S.edges) > 16:
        warn(f'{len(S.edges)} edges (more than 16)')
    if err:
        die('\n  '.join(['invalid spec:'] + err))

    phases = sp.get('phases')
    if not phases:
        phases = derive_phases(S)
    elif S.control == 'loop' and spec_control == 'step':
        phases = [dict(p) for p in phases]
        st = math.floor((S.cycle - 2) / len(phases) * 10) / 10
        for i, p in enumerate(phases):
            p['t'] = round(i * st, 2)
        if phases[-1].get('label') != 'hold':
            phases.append({'t': round(S.cycle - 2, 2), 'label': 'hold'})
        warn('control overridden to loop: phases re-timed evenly with a hold')
    S.phases = check_phases(S, phases, err)
    if err:
        die('\n  '.join(['invalid phases:'] + err))
    return S


def topo_order(S):
    order = [n['id'] for n in S.nodes]
    indeg = {i: 0 for i in order}
    for e in S.edges:
        indeg[e['to']] += 1
    out, ready = [], [i for i in order if indeg[i] == 0]
    while ready:
        ready.sort(key=order.index)
        x = ready.pop(0)
        out.append(x)
        for e in S.edges:
            if e['from'] == x:
                indeg[e['to']] -= 1
                if indeg[e['to']] == 0:
                    ready.append(e['to'])
    return out + [i for i in order if i not in out]


def derive_phases(S):
    order = topo_order(S) if S.arch in ('graph', 'states') else [n['id'] for n in S.nodes]
    if not order:
        return ([{'t': 0, 'label': 'setup'}, {'t': S.cycle - 2, 'label': 'hold'}]
                if S.control == 'loop' else [{'t': 0, 'label': 'start'}, {'t': 1, 'label': 'end'}])
    n, hold, cyc = len(order), 2.0, S.cycle
    st = 0
    while S.control == 'loop':
        st = round((cyc - hold) / n * 2) / 2
        if (n - 1) * st > cyc - hold - 0.8:
            st = math.floor((cyc - hold) / n * 10) / 10
        if st >= 0.8 or cyc >= 15:
            break
        cyc += 1
    if S.control == 'loop' and st < 0.8:
        die(f'{n} nodes do not fit a 15 s loop at 0.8 s per phase; split the spec or write phases')
    if cyc != S.cycle:
        warn(f'derived phases need cycle {cyc} s (was {S.cycle})')
        S.cycle = cyc
    phases, seen = [], set()
    for i, nid in enumerate(order):
        flow = [e['id'] for e in S.edges if e['to'] == nid and e['from'] in seen][:3]
        phases.append({'t': round(i * st, 2) if S.control == 'loop' else i, 'label': nid,
                       'show': [nid], 'active': [nid], 'flow': flow})
        seen.add(nid)
    if S.control == 'loop':
        sinks = [x for x in order if not any(e['from'] == x for e in S.edges)]
        label = 'hold' if 'hold' not in order else 'hold-end'
        phases.append({'t': cyc - hold, 'label': label, 'active': sinks[-1:]})
    return phases


def check_phases(S, phases, err):
    out, labels, twice = [], set(), []
    shown_where = {}
    for i, p in enumerate(phases):
        w = f'phases[{i}]'
        if not isinstance(p, dict) or set(p) - KEYS['phase']:
            err.append(f'{w}: must be a mapping with keys {", ".join(sorted(KEYS["phase"]))}')
            continue
        p = {k: p.get(k) for k in KEYS['phase']}
        for k in ('show', 'active', 'flow'):
            p[k] = [str(x) for x in (p[k] or [])]
        lab = p['label']
        if not (isinstance(lab, str) and ID_RE.fullmatch(lab)) or lab in labels:
            err.append(f'{w}: label {lab!r} must be kebab-case and unique')
        labels.add(lab)
        if not isinstance(p['t'], (int, float)):
            err.append(f'{w}: t must be a number')
            p['t'] = 0
        if p['note']:
            p['note'] = str(p['note'])
            if len(p['note']) > 60:
                warn(f'{w}.note is {len(p["note"])} chars (hint: max ~60)')
        for x in p['show']:
            if x in shown_where:
                twice.append(f'{w}: {x} is already shown in phase {shown_where[x]}')
            shown_where[x] = i
        out.append(p)
    if err:
        return out
    err += twice
    if S.control == 'loop':
        ts = [p['t'] for p in out]
        if ts[0] != 0:
            err.append('the first phase must have t: 0')
        for a, b in zip(ts, ts[1:]):
            if b - a < 0.8:
                err.append(f'phase gap {a} -> {b} is under 0.8 s (or not increasing)')
            elif b - a < 1:
                warn(f'phase gap {a} -> {b} is under 1 s')
        if ts[-1] > S.cycle - 1:
            err.append(f'phase t {ts[-1]} is after cycle - 1 ({S.cycle - 1})')
        if out[-1]['label'] != 'hold':
            warn('the last phase is not labelled hold; the loop has no explicit hold')
        elif out[-1]['show'] or out[-1]['flow']:
            warn('the hold phase should have no show and no flow')
    elif any(p['t'] != i for i, p in enumerate(out)):
        warn('step control: phase t values are taken as 0, 1, 2 ... in list order')
    if len(out) > 8:
        warn(f'{len(out)} phases (more than 8 usually means two stories)')
    known = set(S.node) | set(S.group) | set(S.edge) | {x['id'] for x in S.series + S.events}
    visible = set(S.node) - set(shown_where)
    visible |= {x['id'] for x in S.series + S.events if x['id'] not in shown_where}
    for i, p in enumerate(out):
        for x in p['show'] + p['active'] + p['flow']:
            if x not in known:
                err.append(f'phases[{i}]: unknown id {x!r}')
        visible |= set(p['show'])
        for g in S.groups:
            if g['id'] not in shown_where and any(n.get('group') == g['id'] and n['id'] in visible for n in S.nodes):
                visible.add(g['id'])
        for e in S.edges:
            if e['id'] not in shown_where and e['from'] in visible and e['to'] in visible:
                visible.add(e['id'])
        for x in p['active']:
            if x in known and x not in visible:
                err.append(f'phases[{i}]: active {x} is not visible yet')
        for x in p['flow']:
            if x not in S.edge:
                err.append(f'phases[{i}]: flow {x} is not an edge')
            elif x not in visible or S.edge[x]['from'] not in visible or S.edge[x]['to'] not in visible:
                err.append(f'phases[{i}]: flow {x} is not visible yet')
        if len(p['flow']) > 3:
            err.append(f'phases[{i}]: at most 3 flows per phase')
        if len(p['active']) > 3:
            warn(f'phases[{i}]: {len(p["active"])} active ids (keep to 1-3)')
    return out


# ============================================================================ geometry
def text_w(s, fs, mono=False):
    return len(s) * fs * (0.6 if mono else 0.56)


def wrap(text, fs, maxw, maxlines=2):
    lines, cur = [], ''
    for word in text.split():
        cand = f'{cur} {word}'.strip()
        if cur and text_w(cand, fs) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    lines.append(cur)
    if len(lines) > maxlines:
        lines = lines[:maxlines - 1] + [' '.join(lines[maxlines - 1:])]
    return lines


def lerp(a, b, k):
    return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)


def cubic(p0, c1, c2, p3):
    return (p0, c1, c2, p3)


def straight(p0, p3):
    return (p0, lerp(p0, p3, 1 / 3), lerp(p0, p3, 2 / 3), p3)


def quad(p0, q, p3):
    return (p0, lerp(p0, q, 2 / 3), lerp(p3, q, 2 / 3), p3)


def path_d(c):
    return f'M {pt(c[0])} C {pt(c[1])} {pt(c[2])} {pt(c[3])}'


def bez_mid(c):
    return tuple((c[0][k] + 3 * c[1][k] + 3 * c[2][k] + c[3][k]) / 8 for k in (0, 1))


def arrow_d(c, size=12):
    tip, back = c[3], c[2] if c[2] != c[3] else c[0]
    dx, dy = tip[0] - back[0], tip[1] - back[1]
    ln = math.hypot(dx, dy) or 1
    ux, uy = dx / ln, dy / ln
    bx, by = tip[0] - ux * size, tip[1] - uy * size
    return (f'M {pt(tip)} L {pt((bx - uy * size * 0.5, by + ux * size * 0.5))} '
            f'L {pt((bx + uy * size * 0.5, by - ux * size * 0.5))} Z')


def centre(b):
    return (b['x'] + b['w'] / 2, b['y'] + b['h'] / 2)


def route(a, b, k=None):
    """Cubic between the facing sides of two boxes."""
    (ax, ay), (bx, by) = centre(a), centre(b)
    if abs(bx - ax) >= abs(by - ay):
        s = 1 if bx > ax else -1
        p0, p3 = (ax + s * a['w'] / 2, ay), (bx - s * b['w'] / 2, by)
        kk = k or max(40, min(120, abs(p3[0] - p0[0]) / 2))
        return cubic(p0, (p0[0] + s * kk, p0[1]), (p3[0] - s * kk, p3[1]), p3)
    s = 1 if by > ay else -1
    p0, p3 = (ax, ay + s * a['h'] / 2), (bx, by - s * b['h'] / 2)
    kk = k or max(30, min(100, abs(p3[1] - p0[1]) / 2))
    return cubic(p0, (p0[0], p0[1] + s * kk), (p3[0], p3[1] - s * kk), p3)


def under_arc(a, b, depth=64):
    p0 = (a['x'] + a['w'] / 2, a['y'] + a['h'])
    p3 = (b['x'] + b['w'] / 2, b['y'] + b['h'])
    yc = max(p0[1], p3[1]) + depth
    return cubic(p0, (p0[0], yc), (p3[0], yc), p3)


def over_arc(a, b, depth=64):
    p0, p3 = (a['x'] + a['w'] / 2, a['y']), (b['x'] + b['w'] / 2, b['y'])
    yc = min(p0[1], p3[1]) - depth
    return cubic(p0, (p0[0], yc), (p3[0], yc), p3)


# ============================================================================ layouts
# Every layout returns a scene: nodes {id: box}, edges {edge id: cubic}, containers (panels,
# bands) and `back` markup drawn behind everything. Boxes are dicts x, y, w, h (+ extras).

def frame(S, F):
    top = max(64, F['title'] + 38) if S.title else 24
    strip = max(56, F['note'] + 26)
    has_note = any(p['note'] for p in S.phases)
    bottom = S.H - strip - 16 if has_note else S.H - 24
    return top, bottom, strip, has_note


def layout_pipeline(S, F, top, bottom):
    n, W = len(S.nodes), S.W
    w, h = (240, 120) if n < 7 else (200, 110)
    gap = (W - 80 - n * w) / (n - 1) if n > 1 else 0
    if n > 1 and gap < 60:
        gap = 60
        w = (W - 80 - (n - 1) * gap) / n
    idx = {nd['id']: i for i, nd in enumerate(S.nodes)}
    back = any(idx[e['to']] < idx[e['from']] for e in S.edges)
    cy = (top + bottom) / 2 - (24 if back else 0)
    x0 = (W - (n * w + (n - 1) * gap)) / 2
    nodes = {nd['id']: dict(x=x0 + i * (w + gap), y=cy - h / 2, w=w, h=h) for i, nd in enumerate(S.nodes)}
    edges = {}
    for e in S.edges:
        a, b = nodes[e['from']], nodes[e['to']]
        i, j = idx[e['from']], idx[e['to']]
        if j == i + 1:
            edges[e['id']] = straight((a['x'] + w, cy), (b['x'], cy))
        elif j > i:
            edges[e['id']] = over_arc(a, b)
        else:
            edges[e['id']] = under_arc(a, b)
    return dict(nodes=nodes, edges=edges)


def ranks(S):
    order = [n['id'] for n in S.nodes]
    out = {i: [e['to'] for e in S.edges if e['from'] == i] for i in order}
    state, backs = {}, set()

    def dfs(u):
        state[u] = 1
        for v in out[u]:
            if state.get(v) == 1:
                backs.add(f'{u}>{v}')
            elif v not in state:
                dfs(v)
        state[u] = 2
    for u in order:
        if u not in state:
            dfs(u)
    rank = {i: 0 for i in order}
    for _ in order:
        for e in S.edges:
            if e['id'] not in backs:
                rank[e['to']] = max(rank[e['to']], rank[e['from']] + 1)
    return rank


def layout_graph(S, F, top, bottom):
    rank = ranks(S)
    R = max(rank.values()) + 1
    cols = [[n['id'] for n in S.nodes if rank[n['id']] == r] for r in range(R)]
    nw = 220
    pitch_x = (S.W - 80 - nw) / (R - 1) if R > 1 else 0
    if R > 1 and pitch_x < nw + 60:
        nw = (S.W - 80 - 60 * (R - 1)) / R
        pitch_x = nw + 60
    gtop, gbot = (52, 20) if S.groups else (0, 0)
    lo, hi = top + gtop, bottom - gbot
    rows = max(len(c) + 0.5 * len({S.node[i].get('group') for i in c}) - 0.5 for c in cols)
    pitch_y = min(120, (hi - lo) / rows)
    nh = min(84, pitch_y - 24)
    gidx = {g['id']: i for i, g in enumerate(S.groups)}
    order = [n['id'] for n in S.nodes]
    nodes, mid = {}, (lo + hi) / 2
    x0 = (S.W - (nw + (R - 1) * pitch_x)) / 2
    for r, col in enumerate(cols):
        def key(i):
            parents = [centre(nodes[e['from']])[1] for e in S.edges if e['to'] == i and e['from'] in nodes]
            return (gidx.get(S.node[i].get('group'), len(gidx)),
                    sum(parents) / len(parents) if parents else 0, order.index(i))
        ordered, ys, y = sorted(col, key=key), [], 0.0
        for k, i in enumerate(ordered):      # extra gap where the group changes inside a column
            if k and S.node[i].get('group') != S.node[ordered[k - 1]].get('group'):
                y += 56 if S.groups else 0
            ys.append(y)
            y += pitch_y
        shift = mid - (ys[-1] / 2 if ys else 0)
        for i, yy in zip(ordered, ys):
            nodes[i] = dict(x=x0 + r * pitch_x, y=shift + yy - nh / 2, w=nw, h=nh)
    push_out_of_groups(S, nodes, top, bottom)
    edges = {}
    for e in S.edges:
        a, b = nodes[e['from']], nodes[e['to']]
        if rank[e['to']] > rank[e['from']]:
            edges[e['id']] = route(a, b, k=80)
            continue
        x0e, x1e = sorted((centre(a)[0], centre(b)[0]))   # back edge: arc below every node it spans
        low = max(o['y'] + o['h'] for o in nodes.values() if o['x'] < x1e and o['x'] + o['w'] > x0e)
        base = max(a['y'] + a['h'], b['y'] + b['h'])
        edges[e['id']] = under_arc(a, b, max(60, (low + 36 - base) / 0.75))
    return dict(nodes=nodes, edges=edges)


def group_box(S, nodes, gid):
    bs = [nodes[n['id']] for n in S.nodes if n.get('group') == gid]
    x, y = min(b['x'] for b in bs) - 20, min(b['y'] for b in bs) - 52
    return dict(x=x, y=y, w=max(b['x'] + b['w'] for b in bs) + 20 - x, h=max(b['y'] + b['h'] for b in bs) + 20 - y)


def overlaps(a, b, pad=0):
    return (a['x'] < b['x'] + b['w'] + pad and a['x'] + a['w'] + pad > b['x']
            and a['y'] < b['y'] + b['h'] + pad and a['y'] + a['h'] + pad > b['y'])


def push_out_of_groups(S, nodes, top, bottom):
    """Move a node that sits inside another group's box just below (or above) that box."""
    for g in S.groups:
        box = group_box(S, nodes, g['id'])
        for n in S.nodes:
            b = nodes[n['id']]
            if n.get('group') == g['id'] or not overlaps(b, box, 12):
                continue
            if box['y'] + box['h'] + 16 + b['h'] <= bottom:
                b['y'] = box['y'] + box['h'] + 16
            elif box['y'] - 16 - b['h'] >= top:
                b['y'] = box['y'] - 16 - b['h']


def layout_timeline(S, F, top, bottom):
    n, W = len(S.nodes), S.W
    spacing = (W - 240) / max(1, n - 1)
    alt = n > 5 and spacing < 280
    cw = min(260, (2 * spacing if alt else spacing) - 24)
    m = max(160, 24 + cw / 2)                 # end cards stay inside the viewBox (archetypes.md: x 160 to 1520)
    xs = [W / 2] if n == 1 else [m + i * (W - 2 * m) / (n - 1) for i in range(n)]
    ay = (top + bottom) / 2 + (0 if alt else 44)
    nodes, back = {}, []
    for i, nd in enumerate(S.nodes):
        lines = len(wrap(nd['label'], F['lbl'], cw - 24))
        ch = 20 + lines * F['lbl'] * 1.25 + (F['sub'] * 1.25 if nd['sub'] else 0)
        below = alt and i % 2 == 1
        y = ay + 30 + F['mono'] + 16 if below else ay - 34 - ch
        nodes[nd['id']] = dict(x=xs[i] - cw / 2, y=y, w=cw, h=ch, marker=(xs[i], ay), below=below)
        back.append(f'<circle class="{S.name}-mk" cx="{f1(xs[i])}" cy="{f1(ay)}" r="14"/>'
                    f'<text class="{S.name}-t {S.name}-mono" x="{f1(xs[i])}" y="{f1(ay + 30 + F["mono"] * 0.6)}" '
                    f'text-anchor="middle">{escape(str(nd["at"]))}</text>')
    axis = f'M {f1(xs[0])},{f1(ay)} L {f1(xs[-1] if n > 1 else xs[0] + 1)},{f1(ay)}'
    back.insert(0, f'<path class="{S.name}-axis" d="{axis}"/>')
    back.insert(1, f'<path id="{S.name}-progress" class="{S.name}-prog" d="{axis}" pathLength="100"/>')
    edges = {e['id']: route(nodes[e['from']], nodes[e['to']]) for e in S.edges}
    return dict(nodes=nodes, edges=edges, back=back)


def layout_states(S, F, top, bottom):
    n = len(S.nodes)
    w, h = 200, 72
    for nd in S.nodes:
        w = max(w, min(280, text_w(nd['label'], F['lbl']) + 48))
    cx, cy = S.W / 2, (top + bottom) / 2
    rx, ry = (S.W - 48 - w) / 2 - 40, max(60, (bottom - top - h) / 2 - 26)
    nodes = {}
    for i, nd in enumerate(S.nodes):
        a = math.pi + i * 2 * math.pi / n
        nodes[nd['id']] = dict(x=cx + rx * math.cos(a) - w / 2, y=cy + ry * math.sin(a) - h / 2,
                               w=w, h=h, pill=True)
    edges, idx = {}, {nd['id']: i for i, nd in enumerate(S.nodes)}
    for e in S.edges:
        a, b = nodes[e['from']], nodes[e['to']]
        pa, pb = centre(a), centre(b)
        p0, p3 = clip_box(a, pb), clip_box(b, pa)
        m = lerp(p0, p3, 0.5)
        dx, dy = m[0] - cx, m[1] - cy
        d = math.hypot(dx, dy) or 1
        bulge = 0.18 * math.hypot(p3[0] - p0[0], p3[1] - p0[1]) + 20
        if f'{e["to"]}>{e["from"]}' in S.edge and idx[e['from']] > idx[e['to']]:
            bulge = -bulge
        chord = math.hypot(p3[0] - p0[0], p3[1] - p0[1]) or 1
        if d < 0.15 * chord:            # chord through the centre: bend sideways
            dx, dy, d = -(p3[1] - p0[1]), p3[0] - p0[0], chord
        edges[e['id']] = quad(p0, (m[0] + dx / d * bulge, m[1] + dy / d * bulge), p3)
    return dict(nodes=nodes, edges=edges)


def clip_box(b, toward, pad=4):
    c = centre(b)
    dx, dy = toward[0] - c[0], toward[1] - c[1]
    k = min((b['w'] / 2 + pad) / abs(dx) if dx else 1e9, (b['h'] / 2 + pad) / abs(dy) if dy else 1e9)
    return (c[0] + dx * k, c[1] + dy * k)


def container_label(S, members):
    """A group whose members are exactly these nodes names the panel / band."""
    for g in S.groups:
        gm = {n['id'] for n in S.nodes if n.get('group') == g['id']}
        if gm and gm <= set(members):
            return g
    return None


def layout_compare(S, F, top, bottom):
    W, nodes, conts = S.W, {}, []
    for k, side in enumerate(('left', 'right')):
        px = 24 if k == 0 else W / 2 + 12
        pw = W / 2 - 36
        members = [n['id'] for n in S.nodes if n['side'] == side]
        g = container_label(S, members)
        label = g['label'] if g else ('Before' if k == 0 else 'After')
        conts.append(dict(key=g['id'] if g else f'c-{side}', group=g, x=px, y=top, w=pw, h=bottom - top,
                          label=label, style='panel', members=members))
        hy = top + F['head'] + 40
        pitch = min(84, (bottom - 16 - hy) / max(1, len(members)))
        for r, i in enumerate(members):
            nodes[i] = dict(x=px + 24, y=hy + r * pitch, w=pw - 48, h=min(64, pitch - 12), row=True)
    edges = {e['id']: route(nodes[e['from']], nodes[e['to']]) for e in S.edges}
    return dict(nodes=nodes, edges=edges, containers=conts)


def layout_layers(S, F, top, bottom):
    levels = sorted({n['layer'] for n in S.nodes})
    L = len(levels)
    bh = (bottom - top - (L - 1) * 12) / L
    nodes, conts = {}, []
    name_w = 236
    for li, lv in enumerate(levels):
        y = bottom - (li + 1) * bh - li * 12
        members = [n['id'] for n in S.nodes if n['layer'] == lv]
        g = container_label(S, members)
        conts.append(dict(key=g['id'] if g else f'c-l{lv}', group=g, x=24, y=y, w=S.W - 48, h=bh,
                          label=g['label'] if g else f'Layer {lv}', style='band', members=members, order=li))
        slot = (S.W - 48 - name_w) / len(members)
        cw, ch = min(220, slot - 20), min(64, bh - 20)
        for k, i in enumerate(members):
            nodes[i] = dict(x=name_w + k * slot + (slot - cw) / 2, y=y + (bh - ch) / 2, w=cw, h=ch)
    edges = {}
    for e in S.edges:
        a, b = nodes[e['from']], nodes[e['to']]
        if abs(centre(a)[1] - centre(b)[1]) < 1:
            edges[e['id']] = route(a, b)
            continue
        down = centre(b)[1] > centre(a)[1]
        off = -12 if down else 12
        p0 = (centre(a)[0] + off, a['y'] + (a['h'] if down else 0))
        p3 = (centre(b)[0] + off, b['y'] + (0 if down else b['h']))
        ym = (p0[1] + p3[1]) / 2
        edges[e['id']] = cubic(p0, (p0[0], ym), (p3[0], ym), p3)
    return dict(nodes=nodes, edges=edges, containers=conts)


def nice(span, n):
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    return next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)


def num(v):
    return f'{v:.6g}'


def layout_chart(S, F, top, bottom):
    N = S.name
    xs = [p[0] for s in S.series for p in s['points']]
    ys = [p[1] for s in S.series for p in s['points']]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    span = (y1 - y0) or abs(y1) or 1
    lo = 0 if 0 <= y0 <= 0.5 * y1 else y0 - 0.05 * span
    hi = y1 + 0.05 * span
    ystep = nice(hi - lo, 5)
    yt = [k * ystep for k in range(math.ceil(lo / ystep - 1e-9), math.floor(hi / ystep + 1e-9) + 1)]
    lo, hi = min(lo, yt[0]), max(hi, yt[-1])
    L = max(120, 40 + max(text_w(num(v), F['mono'], True) for v in yt))
    R = S.W - 24 - max(text_w(s['label'], F['lbl']) for s in S.series) - 16
    T = top + (F['mono'] + 34 if S.events else 16)
    B = bottom - F['mono'] - 24
    X = lambda x: L + (x - x0) / ((x1 - x0) or 1) * (R - L)   # noqa: E731
    Y = lambda y: B - (y - lo) / ((hi - lo) or 1) * (B - T)   # noqa: E731
    back = []
    for v in yt:
        back.append(f'<path class="{N}-grid" d="M {f1(L)},{f1(Y(v))} H {f1(R)}"/>'
                    f'<text class="{N}-t {N}-mono" x="{f1(L - 12)}" y="{f1(Y(v) + F["mono"] * 0.35)}" '
                    f'text-anchor="end">{num(v)}</text>')
    xstep = nice(x1 - x0 or 1, 6)
    for k in range(math.ceil(x0 / xstep - 1e-9), math.floor(x1 / xstep + 1e-9) + 1):
        back.append(f'<text class="{N}-t {N}-mono" x="{f1(X(k * xstep))}" y="{f1(B + F["mono"] + 12)}" '
                    f'text-anchor="middle">{num(k * xstep)}</text>')
    back.append(f'<path class="{N}-axis" d="M {f1(L)},{f1(T)} V {f1(B)} H {f1(R)}"/>')
    series = []
    for k, s in enumerate(S.series):
        p = [(X(a), Y(b)) for a, b in s['points']]
        series.append(dict(s=s, k=k, pts=p, frac=[(a - x0) / ((x1 - x0) or 1) for a, _ in s['points']],
                           d='M ' + ' L '.join(pt(q) for q in p)))
    ends = sorted(range(len(series)), key=lambda i: series[i]['pts'][-1][1])
    last = -1e9
    for i in ends:                       # end-of-line labels: keep them apart vertically
        y = max(series[i]['pts'][-1][1] + F['lbl'] * 0.35, last + F['lbl'] * 1.2)
        series[i]['ly'] = last = y
    events = [dict(e=e, x=X(e['at']), frac=(e['at'] - x0) / ((x1 - x0) or 1)) for e in S.events]
    return dict(nodes={}, edges={}, back=back, chart=dict(L=L, R=R, T=T, B=B, series=series, events=events))


LAYOUTS = {'pipeline': layout_pipeline, 'graph': layout_graph, 'timeline': layout_timeline,
           'states': layout_states, 'compare': layout_compare, 'layers': layout_layers,
           'chart': layout_chart}


# ============================================================================ timing
class Timing:
    """Phase times for both controls. loop: seconds from the spec; step: one label per STEP s,
    with each phase's tweens placed in the STEP before its label so tweenTo(label) plays them."""

    def __init__(self, S):
        self.loop = S.control == 'loop'
        n = len(S.phases)
        if self.loop:
            self.t = [float(p['t']) for p in S.phases]
            self.end, self.rst = float(S.cycle), S.cycle - RESET
            self.act = list(self.t)
            self.win = [(self.t[i + 1] if i + 1 < n else self.rst) - self.t[i] for i in range(n)]
            self.draw_end = self.t[-1] if n > 1 else self.rst
        else:
            self.t = [i * STEP for i in range(n)]
            self.end = self.rst = self.t[-1]
            self.act = [0.0] + [t - STEP + 0.1 for t in self.t[1:]]
            self.win = [STEP - 0.2] * n
            self.draw_end = self.end
        self.n = n

    def xtime(self, frac):
        if self.loop:
            return frac * self.draw_end
        if self.n < 2:
            return 0.0
        pos = frac * (self.n - 1)
        i = max(1, math.ceil(pos - 1e-9))
        return self.act[i] + (pos - (i - 1)) * self.win[i]

    def phase_at(self, t):
        return max([i for i in range(self.n) if self.act[i] <= t + 1e-6] or [0])


class Anim:
    def __init__(self):
        self.segs, self.rest_over = {}, {}

    def add(self, el, prop, t0, dur, v0, v1, ease='enter'):
        self.segs.setdefault(el, []).append((prop, round(t0, 2), round(max(dur, 0.05), 2), v0, v1, ease))

    def rest(self, el):
        out = {}
        for prop, t0, dur, v0, v1, ease in sorted(self.segs.get(el, []), key=lambda s: s[1]):
            out[prop] = v1
        out.update(self.rest_over.get(el, {}))
        return out

    def style(self, el, extra=''):
        r = self.rest(el)
        s = ';'.join(f'{k}:{v}' for k, v in r.items())
        s = ';'.join(x for x in (extra, s) if x)
        return f' style="{s}"' if s else ''


def build_anims(S, T, scene, anim):
    N = S.name
    rid = rendered_ids(S, scene)
    entry = {}

    def stagger(k, m):
        return 0 if m < 2 else k * min(0.08, (0.45 if T.loop else 0.25) / (m - 1))

    for i, p in enumerate(S.phases):
        for k, x in enumerate(p['show']):
            entry[x] = (T.act[i] + stagger(k, len(p['show'])), i)
    implicit = [n['id'] for n in S.nodes if n['id'] not in entry]
    for k, x in enumerate(implicit):
        entry[x] = (stagger(k, len(implicit)), 0)
    for c in scene.get('containers', []):
        if c['group'] is None or c['key'] not in entry:
            ms = [entry[m] for m in c['members']] or [(0, 0)]
            entry[c['key']] = (min(ms)[0] + (0.1 * c.get('order', 0) if min(ms)[1] == 0 else 0), min(ms)[1])
    for g in S.groups:
        if g['id'] not in entry:
            entry[g['id']] = min(entry[n['id']] for n in S.nodes if n.get('group') == g['id'])
    for e in S.edges:
        if e['id'] not in entry:
            a, b = max(entry[e['from']], entry[e['to']])
            entry[e['id']] = (a + (0.3 if T.loop else 0.15), b)
    ch = scene.get('chart')
    if ch:
        for s in ch['series']:
            s['drawn'] = s['s']['id'] not in entry
            entry.setdefault(s['s']['id'], (0, 0))
        for ev in ch['events']:
            if ev['e']['id'] not in entry:
                t = T.xtime(ev['frac'])
                entry[ev['e']['id']] = (t, T.phase_at(t))

    for key, (t, i) in entry.items():
        if key not in rid or (not T.loop and i == 0):
            continue
        anim.add(rid[key], 'opacity', t, 0.4, 0, 1)
        if key in S.edge and S.edge[key]['kind'] in ('flow', 'data'):
            anim.add(rid[key] + '-w', 'stroke-dashoffset', t, 0.6, 100, 0, 'move')

    # highlights and notes: runs of consecutive phases
    def runs(on, el):
        i = 0
        while i < T.n:
            if not on[i]:
                i += 1
                continue
            j = i
            while j + 1 < T.n and on[j + 1]:
                j += 1
            if T.loop or i > 0:
                anim.add(el, 'opacity', T.act[i], 0.25 if T.loop else 0.2, 0, 1)
            if j + 1 < T.n:
                anim.add(el, 'opacity', T.act[j + 1], 0.2, 1, 0, 'exit')
            i = j + 1
        anim.rest_over[el] = {'opacity': 1 if on[-1] else 0}
    for key in sorted({x for p in S.phases for x in p['active']}):
        if key in rid and key not in {s['id'] for s in S.series + S.events}:
            runs([key in p['active'] for p in S.phases], rid[key] + '-hl')
    notes = [i for i, p in enumerate(S.phases) if p['note']]
    for k, i in enumerate(notes):
        nxt = notes[k + 1] if k + 1 < len(notes) else T.n
        runs([i <= j < nxt for j in range(T.n)], f'{N}-note{k}')

    # packets
    pk = 0
    for i, p in enumerate(S.phases):
        pos = {}
        for eid in p['flow']:
            pos[eid] = max([pos[f] + 1 for f in pos if S.edge[f]['to'] == S.edge[eid]['from']], default=0)
        depth = max(pos.values(), default=0) + 1
        lo, hi = (0.6, 1.0) if T.loop else (0.3, 0.8)
        hop = max(lo, min(hi, T.win[i] / depth - 0.3))
        for eid in p['flow']:
            el, t0 = f'{N}-p{pk}', T.act[i] + 0.05 + pos[eid] * (hop + 0.3)
            anim.add(el, 'opacity', t0, 0.1, 0, 1, 'linear')
            anim.add(el, 'offset-distance', t0 + 0.1, hop, '0%', '100%', 'move')
            anim.add(el, 'opacity', t0 + 0.1 + hop, 0.15, 1, 0, 'exit')
            scene.setdefault('packets', []).append((el, eid))
            pk += 1

    if S.arch == 'timeline':                      # progress line reaches each milestone as it enters
        n, cur, last = len(S.nodes), 100.0, 0.0
        for i, nd in sorted(enumerate(S.nodes), key=lambda x: entry[x[1]['id']][0]):
            v = 100 - 100 * i / max(1, n - 1)
            t, ph = entry[nd['id']]
            if v < cur and (T.loop or ph > 0):
                t0 = max(last, t - 0.6)
                anim.add(f'{N}-progress', 'stroke-dashoffset', t0, max(0.2, t - t0), cur, v, 'move')
                last = t
            if v < cur:
                cur = v
        anim.rest_over[f'{N}-progress'] = {'stroke-dashoffset': 0}
    if ch:
        pw = ch['R'] - ch['L']
        if T.loop:
            anim.add(f'{N}-clip-r', 'width', 0, T.draw_end, '0px', f'{f1(pw)}px', 'linear')
        else:
            for i in range(1, T.n):
                anim.add(f'{N}-clip-r', 'width', T.act[i], T.win[i], f'{f1(pw * (i - 1) / (T.n - 1))}px',
                         f'{f1(pw * i / (T.n - 1))}px', 'linear')
        for s in ch['series']:
            sid = rid[s['s']['id']]
            if not s['drawn']:
                continue
            anim.add(sid + '-end', 'opacity', T.xtime(1) - (0.3 if T.loop else 0), 0.3, 0, 1)
            if not T.loop:
                anim.add(sid + '-dot', 'opacity', T.act[-1], 0.2, 0, 1)
                continue
            step = max(1, math.ceil(len(s['pts']) / 30))
            idx = list(range(0, len(s['pts']), step))
            if idx[-1] != len(s['pts']) - 1:
                idx.append(len(s['pts']) - 1)
            for a, b in zip(idx, idx[1:]):
                ta, tb = T.xtime(s['frac'][a]), T.xtime(s['frac'][b])
                pa, pb = s['pts'][a], s['pts'][b]
                anim.add(sid + '-dot', 'transform', ta, tb - ta, f'translate({f1(pa[0])}px,{f1(pa[1])}px)',
                         f'translate({f1(pb[0])}px,{f1(pb[1])}px)', 'linear')
    return rid


def rendered_ids(S, scene):
    N = S.name
    rid = {n['id']: f'{N}-n-{n["id"]}' for n in S.nodes}
    rid.update({g['id']: f'{N}-g-{g["id"]}' for g in S.groups})
    rid.update({e['id']: f'{N}-e-{e["from"]}-{e["to"]}' for e in S.edges})
    rid.update({s['id']: f'{N}-s-{s["id"]}' for s in S.series})
    rid.update({e['id']: f'{N}-v-{e["id"]}' for e in S.events})
    for c in scene.get('containers', []):
        rid.setdefault(c['key'], f'{N}-{c["key"]}')
    return rid


# ============================================================================ emit
def css_keyframes(el, segs, T, marks):
    stops = {}

    def put(t, prop, v, ease=None):
        t = round(min(max(t, 0), T.end), 2)
        s = stops.setdefault(t, [{}, None])
        s[0][prop] = v
        if ease and not s[1]:
            s[1] = ease
    byprop = {}
    for s in segs:
        byprop.setdefault(s[0], []).append(s)
    for prop, ss in byprop.items():
        ss.sort(key=lambda s: s[1])
        init = cur = ss[0][3]
        last = 0
        put(0, prop, init)
        for _, t0, dur, v0, v1, ease in ss:
            t0 = max(t0, last)
            if t0 >= T.rst:
                continue
            t1 = min(t0 + dur, T.rst)
            put(t0, prop, cur, ease)
            put(t1, prop, v1)
            last, cur = t1, v1
        put(T.rst, prop, cur, 'exit')
        put(T.end, prop, init)
    out = [f'@keyframes {el} {{']
    for t in sorted(stops):
        props, ease = stops[t]
        body = ' '.join(f'{k}: {v};' for k, v in props.items())
        if ease:
            body += f' animation-timing-function: {EASE[ease][0]};'
        pct = f'{t / T.end * 100:.2f}'.rstrip('0').rstrip('.')
        out.append(f'  {pct}% {{ {body} }}  /* {f1(t)}s{" " + marks[t] if t in marks else ""} */')
    return '\n'.join(out + ['}'])


GSAP_PROP = {'opacity': 'opacity', 'stroke-dashoffset': 'strokeDashoffset',
             'offset-distance': 'offsetDistance', 'width': 'width'}


def js_val(v):
    return json.dumps(v) if isinstance(v, str) else f1(v)


def gsap_script(S, T, anim):
    N = S.name
    L = ['<script type="module">',
         '// step control: a paused GSAP timeline, one label per phase; scripts/snippets/step-host.html',
         '// tweens to the next/previous label. Tweens of phase i end just before its label.',
         'const gsap = window.gsap;',
         f'const root = document.querySelector(\'[data-anim="{N}"]\');',
         'if (gsap && root) {',
         '  const tl = gsap.timeline({ paused: true });',
         '  // the first tween per element and property renders immediately, so rewinding to the',
         '  // first label restores its from-state (later ones would revert to the resting frame)',
         "  const T = (id, from, to, at, first) => tl.fromTo(root.querySelector('#' + id), from,",
         '    Object.assign({ immediateRender: !!first, lazy: false }, to), at);']
    for i, p in enumerate(S.phases):
        L.append(f"  tl.addLabel('{p['label']}', {f1(T.t[i])});")
    items = sorted(((t0, el, prop, dur, v0, v1, ease) for el, segs in anim.segs.items()
                    for prop, t0, dur, v0, v1, ease in segs if prop in GSAP_PROP), key=lambda x: x[0])
    seen = set()
    for t0, el, prop, dur, v0, v1, ease in items:
        k, first = GSAP_PROP[prop], (el, prop) not in seen
        seen.add((el, prop))
        L.append(f"  T('{el}', {{ {k}: {js_val(v0)} }}, {{ {k}: {js_val(v1)}, duration: {f1(dur)}, "
                 f"ease: '{EASE[ease][1]}' }}, {f1(t0)}{', 1' if first else ''});")
    L += [f'  tl.set({{}}, {{}}, {f1(T.end)});   // timeline reaches the last label',
          '  tl.progress(1);   // show the resting frame until the host seeks to the first label',
          '  var A = window.animSlides = window.animSlides || {};',
          f"  if (A.register) A.register('{N}', tl); else (A.q = A.q || []).push(['{N}', tl]);",
          '}', '</script>']
    return '\n'.join(L)


def text_lines(cx, y, h, lines, anchor='middle'):
    total = sum(fs * 1.25 for _, _, fs in lines) - lines[-1][2] * 0.25
    yt, out = y + (h - total) / 2, []
    for txt, cls, fs in lines:
        out.append(f'<text class="{cls}" x="{f1(cx)}" y="{f1(yt + fs * 0.8)}" '
                   f'text-anchor="{anchor}">{escape(txt)}</text>')
        yt += fs * 1.25
    return ''.join(out), total


def shape(kind, b, cls, rx=8, el_id='', style=''):
    x, y, w, h = b['x'], b['y'], b['w'], b['h']
    a = f' class="{cls}"' + (f' id="{el_id}"' if el_id else '') + style
    if b.get('pill'):
        rx = h / 2
    if kind == 'store':
        e = min(12, h / 6)
        return (f'<path{a} d="M {pt((x, y + e))} A {f1(w / 2)},{f1(e)} 0 0 1 {pt((x + w, y + e))} '
                f'V {f1(y + h - e)} A {f1(w / 2)},{f1(e)} 0 0 1 {pt((x, y + h - e))} Z"/>')
    if kind == 'data':
        f = 18
        return f'<path{a} d="M {pt((x, y))} H {f1(x + w - f)} L {pt((x + w, y + f))} V {f1(y + h)} H {f1(x)} Z"/>'
    return f'<rect{a} x="{f1(x)}" y="{f1(y)}" width="{f1(w)}" height="{f1(h)}" rx="{f1(rx)}"/>'


def glyph(N, kind, b):
    x, y, w, h = b['x'], b['y'], b['w'], b['h']
    c = f'{N}-glyph'
    if kind == 'actor':
        return (f'<circle class="{c}" cx="{f1(x + 22)}" cy="{f1(y + 18)}" r="6"/>'
                f'<path class="{c}" d="M {pt((x + 12, y + 36))} Q {pt((x + 22, y + 22))} {pt((x + 32, y + 36))}"/>')
    if kind == 'decision':
        return f'<path class="{c}" d="M {pt((x + 22, y + 10))} l 10,10 l -10,10 l -10,-10 Z"/>'
    if kind == 'store':
        e = min(12, h / 6)
        return f'<path class="{c}" d="M {pt((x, y + e))} A {f1(w / 2)},{f1(e)} 0 0 0 {pt((x + w, y + e))}"/>'
    if kind == 'data':
        return f'<path class="{c}" d="M {pt((x + w - 18, y))} V {f1(y + 18)} H {f1(x + w)}"/>'
    if kind == 'milestone' and 'marker' not in b:
        return f'<path class="{c}" d="M {pt((x + 16, y + 34))} V {f1(y + 10)} l 14,6 l -14,6"/>'
    return ''


def emit(S, args, F, scene, T, anim, rid, frame_info):
    N = S.name
    top, bottom, strip, has_note = frame_info
    active_ids = {x for p in S.phases for x in p['active']}
    over = []                                       # overflow warnings
    svg = []
    if S.title:
        svg.append(f'<text class="{N}-t {N}-title" x="24" y="{f1(top - 22)}">{escape(S.title)}</text>')
    svg += scene.get('back', [])

    for c in scene.get('containers', []):
        el = rid[c['key']]
        hl = (f'<rect id="{el}-hl" class="{N}-hl" x="{f1(c["x"])}" y="{f1(c["y"])}" width="{f1(c["w"])}" '
              f'height="{f1(c["h"])}" rx="8"{anim.style(el + "-hl")}/>' if c['key'] in active_ids else '')
        if c['style'] == 'panel':
            lab = (f'<text class="{N}-t {N}-head" x="{f1(c["x"] + c["w"] / 2)}" y="{f1(c["y"] + F["head"] + 14)}" '
                   f'text-anchor="middle">{escape(c["label"])}</text>')
        else:
            lab = (f'<text class="{N}-t {N}-sub" x="48" y="{f1(c["y"] + c["h"] / 2 + F["sub"] * 0.35)}">'
                   f'{escape(c["label"])}</text>')
        svg.append(f'<g id="{el}" class="{N}-cont"{anim.style(el)}><rect class="{N}-panel" x="{f1(c["x"])}" '
                   f'y="{f1(c["y"])}" width="{f1(c["w"])}" height="{f1(c["h"])}" rx="8"/>{hl}{lab}</g>')
    used = {c['group']['id'] for c in scene.get('containers', []) if c['group']}
    for g in S.groups:
        if g['id'] in used:
            continue
        box = group_box(S, scene['nodes'], g['id'])
        x, y = box['x'], box['y']
        for n in S.nodes:
            if n.get('group') != g['id'] and overlaps(scene['nodes'][n['id']], box):
                warn(f'group {g["id"]} box overlaps node {n["id"]}; move it by hand')
        el = rid[g['id']]
        hl = shape('process', box, f'{N}-hl', el_id=el + '-hl', style=anim.style(el + '-hl')) \
            if g['id'] in active_ids else ''
        svg.append(f'<g id="{el}" class="{N}-group"{anim.style(el)}>{shape("process", box, N + "-grp")}{hl}'
                   f'<text class="{N}-t {N}-sub" x="{f1(x + 16)}" y="{f1(y + 18 + F["sub"] * 0.5)}">'
                   f'{escape(g["label"])}</text></g>')

    for e in S.edges:
        c, el = scene['edges'][e['id']], rid[e['id']]
        draw = e['kind'] in ('flow', 'data')
        wire = (f'<path id="{el}-w" class="{N}-wire{" " + N + "-draw" if draw else ""}" d="{path_d(c)}"'
                f'{" pathLength=" + chr(34) + "100" + chr(34) if draw else ""}{anim.style(el + "-w")}/>')
        hl = (f'<path id="{el}-hl" class="{N}-wire-hl" d="{path_d(c)}"{anim.style(el + "-hl")}/>'
              if e['id'] in active_ids else '')
        lab = ''
        if e['label']:
            m = bez_mid(c)
            ly = m[1] - 10 if abs(c[3][1] - c[0][1]) < 4 and abs(c[1][1] - c[0][1]) < 4 else m[1] + F['edge'] * 0.35
            tw = text_w(e['label'], F['edge'], True) + 12
            lab = (f'<rect class="{N}-lbg" x="{f1(m[0] - tw / 2)}" y="{f1(ly - F["edge"] * 0.9)}" width="{f1(tw)}" '
                   f'height="{f1(F["edge"] * 1.25)}" rx="4"/><text class="{N}-t {N}-mono" x="{f1(m[0])}" '
                   f'y="{f1(ly)}" text-anchor="middle">{escape(e["label"])}</text>')
        svg.append(f'<g id="{el}" class="{N}-edge {N}-ek-{e["kind"]}"{anim.style(el)}>{wire}{hl}'
                   f'<path class="{N}-arrow" d="{arrow_d(c)}"/>{lab}</g>')

    for n in S.nodes:
        b, el, kind = scene['nodes'][n['id']], rid[n['id']], n['kind']
        parts = []
        if 'marker' in b:
            mx, my = b['marker']
            ty = b['y'] if b['below'] else b['y'] + b['h']
            parts.append(f'<path class="{N}-tick" d="M {pt((mx, my + (16 if b["below"] else -16)))} V {f1(ty)}"/>'
                         f'<circle class="{N}-mkfill" cx="{f1(mx)}" cy="{f1(my)}" r="9"/>')
            kind = 'process'
        parts.append(shape(kind, b, f'{N}-box'))
        if n['id'] in active_ids:
            parts.append(shape(kind, b, f'{N}-hl', el_id=el + '-hl', style=anim.style(el + '-hl')))
        g = glyph(N, kind, b)
        parts.append(g)
        mono = ' ' + N + '-monolbl' if n['kind'] == 'data' else ''
        if b.get('row'):
            ty = b['y'] + b['h'] / 2 + F['lbl'] * 0.35
            parts.append(f'<text class="{N}-t {N}-lbl{mono}" x="{f1(b["x"] + 20)}" y="{f1(ty)}">{escape(n["label"])}</text>')
            used_w = text_w(n['label'], F['lbl']) + 40
            if n['sub']:
                parts.append(f'<text class="{N}-t {N}-sub" x="{f1(b["x"] + b["w"] - 20)}" y="{f1(ty)}" '
                             f'text-anchor="end">{escape(n["sub"])}</text>')
                used_w += text_w(n['sub'], F['sub']) + 24
            if used_w > b['w']:
                over.append(n['id'])
        else:
            maxw = b['w'] - (64 if g else 24)
            lines = [(t, f'{N}-t {N}-lbl{mono}', F['lbl']) for t in wrap(n['label'], F['lbl'], maxw)]
            if n['sub']:
                lines.append((n['sub'], f'{N}-t {N}-sub', F['sub']))
            txt, total = text_lines(b['x'] + b['w'] / 2, b['y'], b['h'], lines)
            parts.append(txt)
            if total > b['h'] - 6 or any(text_w(t, fs) > b['w'] - 12 for t, _, fs in lines):
                over.append(n['id'])
        svg.append(f'<g id="{el}" class="{N}-node {N}-k-{n["kind"]}"{anim.style(el)}>{"".join(parts)}</g>')
    if over:
        warn(f'text may overflow its box in node(s) {", ".join(over)}: shorten the label, '
             'use sub, or pick a larger --viewbox / --rendered-width')

    ch = scene.get('chart')
    if ch:
        L, R, Tp, B = ch['L'], ch['R'], ch['T'], ch['B']
        svg.append(f'<clipPath id="{N}-clip"><rect id="{N}-clip-r" x="{f1(L - 4)}" y="{f1(Tp - 12)}" '
                   f'width="{f1(R - L)}" height="{f1(B - Tp + 24)}"{anim.style(N + "-clip-r")}/></clipPath>')
        for ev in ch['events']:
            el, x = rid[ev['e']['id']], ev['x']
            tw = text_w(ev['e']['label'], F['mono'], True) + 20
            tx = min(max(x, L + tw / 2), R - tw / 2)
            svg.append(f'<g id="{el}" class="{N}-event"{anim.style(el)}><path class="{N}-evl" '
                       f'd="M {f1(x)},{f1(Tp)} V {f1(B)}"/><rect class="{N}-chip" x="{f1(tx - tw / 2)}" '
                       f'y="{f1(Tp - F["mono"] - 26)}" width="{f1(tw)}" height="{f1(F["mono"] + 16)}" rx="6"/>'
                       f'<text class="{N}-t {N}-mono" x="{f1(tx)}" y="{f1(Tp - 18 - F["mono"] * 0.15)}" '
                       f'text-anchor="middle">{escape(ev["e"]["label"])}</text></g>')
        for s in ch['series']:
            el, k = rid[s['s']['id']], s['k']
            clip = f' clip-path="url(#{N}-clip)"' if s['drawn'] else ''
            ex, ey = s['pts'][-1]
            dot = (f'<circle id="{el}-dot" class="{N}-dot {N}-f{k}" cx="0" cy="0" r="7"'
                   f'{anim.style(el + "-dot") or " style=" + chr(34) + f"transform:translate({f1(ex)}px,{f1(ey)}px)" + chr(34)}/>'
                   if s['drawn'] else '')
            if dot and 'transform' not in anim.rest(el + '-dot'):
                dot = dot.replace(f'cx="0" cy="0"', f'cx="{f1(ex)}" cy="{f1(ey)}"')
            svg.append(f'<g id="{el}" class="{N}-series"{anim.style(el)}><path class="{N}-ser {N}-c{k}" '
                       f'd="{s["d"]}"{clip}/>{dot}<text id="{el}-end" class="{N}-t {N}-lbl {N}-f{k}" '
                       f'x="{f1(ex + 12)}" y="{f1(s["ly"])}"{anim.style(el + "-end")}>{escape(s["s"]["label"])}</text></g>')

    for el, eid in scene.get('packets', []):
        e = S.edge[eid]
        r = 12 if S.arch == 'states' else 8
        svg.append(f'<circle id="{el}" class="{N}-pkt{" " + N + "-pkt-event" if e["kind"] == "event" else ""}" '
                   f'r="{r}"{anim.style(el, "offset-path:path(" + chr(39) + path_d(scene["edges"][eid]) + chr(39) + ")")}/>')

    if has_note:
        notes = [p['note'] for p in S.phases if p['note']]
        svg.append(f'<rect class="{N}-strip" x="24" y="{f1(S.H - strip - 8)}" width="{f1(S.W - 48)}" '
                   f'height="{f1(strip)}" rx="8"/>')
        for k, t in enumerate(notes):
            if text_w(t, F['note']) > S.W - 80:
                warn(f'note {t[:30]!r}... is wider than the caption strip')
            svg.append(f'<text id="{N}-note{k}" class="{N}-t {N}-note" x="{f1(S.W / 2)}" '
                       f'y="{f1(S.H - 8 - strip / 2 + F["note"] * 0.35)}" text-anchor="middle"'
                       f'{anim.style(f"{N}-note{k}")}>{escape(t)}</text>')
    return svg


def css(S, F, T, anim):
    N, A = S.name, f'.anim-{S.name}'
    rules = f"""{A} {{
  --anim-bg:       var(--anim-theme-bg,       #0f1218);
  --anim-panel:    var(--anim-theme-panel,    #1a2030);
  --anim-line:     var(--anim-theme-line,     #3a4660);
  --anim-fg:       var(--anim-theme-fg,       #eef2f8);
  --anim-muted:    var(--anim-theme-muted,    #9aa7bd);
  --anim-accent:   var(--anim-theme-accent,   #4cc2ff);
  --anim-accent-2: var(--anim-theme-accent-2, #ffb454);
  --anim-ok:       var(--anim-theme-ok,       #3ecf8e);
  --anim-warn:     var(--anim-theme-warn,     #ffb454);
  --anim-danger:   var(--anim-theme-danger,   #ff5d5d);
  --anim-font:     var(--anim-theme-font,     system-ui, sans-serif);
  --anim-mono:     var(--anim-theme-mono,     ui-monospace, monospace);
  display: block; width: 100%; height: 100%;
}}
{A} svg {{ display: block; width: 100%; height: 100%; max-width: none; overflow: visible; }}
{A} .{N}-t {{ font-family: var(--anim-font); fill: var(--anim-fg); }}
{A} .{N}-title {{ font-size: {F['title']}px; font-weight: 700; }}
{A} .{N}-head {{ font-size: {F['head']}px; font-weight: 700; }}
{A} .{N}-lbl {{ font-size: {F['lbl']}px; font-weight: 600; }}
{A} .{N}-monolbl {{ font-family: var(--anim-mono); }}
{A} .{N}-sub {{ font-size: {F['sub']}px; fill: var(--anim-muted); }}
{A} .{N}-mono {{ font-family: var(--anim-mono); font-size: {F['mono']}px; fill: var(--anim-muted); }}
{A} .{N}-note {{ font-size: {F['note']}px; }}
{A} .{N}-box {{ fill: var(--anim-panel); stroke: var(--anim-line); stroke-width: 2; }}
{A} .{N}-k-actor .{N}-box {{ stroke: var(--anim-fg); }}
{A} .{N}-k-decision .{N}-box {{ stroke: var(--anim-accent-2); }}
{A} .{N}-k-external .{N}-box {{ stroke: var(--anim-muted); stroke-dasharray: 8 6; }}
{A} .{N}-glyph {{ fill: none; stroke: var(--anim-muted); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }}
{A} .{N}-hl {{ fill: color-mix(in srgb, var(--anim-accent) 14%, var(--anim-panel)); stroke: var(--anim-accent); stroke-width: 3; }}
{A} .{N}-cont .{N}-hl, {A} .{N}-group .{N}-hl {{ fill: none; }}
{A} .{N}-grp {{ fill: color-mix(in srgb, var(--anim-accent) 6%, transparent); stroke: var(--anim-line); stroke-width: 1.5; }}
{A} .{N}-panel {{ fill: var(--anim-panel); stroke: var(--anim-line); stroke-width: 1.5; }}
{A} .{N}-wire {{ fill: none; stroke: var(--anim-line); stroke-width: 2.5; stroke-linecap: round; }}
{A} .{N}-draw {{ stroke-dasharray: 100; stroke-dashoffset: 0; }}
{A} .{N}-ek-depends .{N}-wire {{ stroke-dasharray: 10 8; }}
{A} .{N}-ek-event .{N}-wire {{ stroke-dasharray: 2 8; }}
{A} .{N}-ek-data .{N}-wire {{ stroke-width: 1.5; }}
{A} .{N}-wire-hl {{ fill: none; stroke: var(--anim-accent); stroke-width: 3.5; stroke-linecap: round; }}
{A} .{N}-arrow {{ fill: var(--anim-line); }}
{A} .{N}-lbg {{ fill: var(--anim-bg); }}
{A} .{N}-pkt {{ fill: var(--anim-accent); }}
{A} .{N}-pkt-event {{ fill: var(--anim-warn); }}
{A} .{N}-strip {{ fill: var(--anim-panel); }}
{A} .{N}-axis {{ fill: none; stroke: var(--anim-line); stroke-width: 3; stroke-linecap: round; }}
{A} .{N}-prog {{ fill: none; stroke: var(--anim-accent); stroke-width: 5; stroke-linecap: round; stroke-dasharray: 100; stroke-dashoffset: 0; }}
{A} .{N}-mk {{ fill: var(--anim-bg); stroke: var(--anim-line); stroke-width: 3; }}
{A} .{N}-mkfill {{ fill: var(--anim-accent); }}
{A} .{N}-tick {{ fill: none; stroke: var(--anim-line); stroke-width: 1.5; }}
{A} .{N}-grid {{ fill: none; stroke: var(--anim-line); stroke-width: 1.5; opacity: 0.6; }}
{A} .{N}-ser {{ fill: none; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }}
{A} .{N}-c0 {{ stroke: var(--anim-accent); }}
{A} .{N}-c1 {{ stroke: var(--anim-accent-2); }}
{A} .{N}-c2 {{ stroke: var(--anim-ok); }}
{A} .{N}-f0 {{ fill: var(--anim-accent); }}
{A} .{N}-f1 {{ fill: var(--anim-accent-2); }}
{A} .{N}-f2 {{ fill: var(--anim-ok); }}
{A} .{N}-evl {{ fill: none; stroke: var(--anim-muted); stroke-width: 2; stroke-dasharray: 6 6; }}
{A} .{N}-chip {{ fill: var(--anim-panel); stroke: var(--anim-line); stroke-width: 1.5; }}
"""
    out = [rules]
    if T.loop:
        marks = {}
        for i, p in enumerate(S.phases):
            marks[round(T.t[i], 2)] = p['label']
        marks[round(T.rst, 2)] = 'reset'
        out.append(f'/* ---- motion: one full-cycle track per element, gated on .visible (cycle {f1(T.end)} s) ---- */')
        for el in anim.segs:
            out.append(f'.visible {A} #{el} {{ animation: {el} {f1(T.end)}s linear infinite; }}')
        for el, segs in anim.segs.items():
            out.append(css_keyframes(el, segs, T, marks))
    else:
        out.append('/* step control: the module script below drives the motion with GSAP */')
    out.append(f'@media (prefers-reduced-motion: reduce) {{ {A} * {{ animation: none !important; }} }}')
    return '\n'.join(out)


REFINE = {
    'pipeline': 'status chips above boxes; settle finished boxes to --anim-ok; feedback arc colour',
    'graph': 'dim non-active nodes to 60 %; reroute edges that cross nodes or skip columns',
    'timeline': 'past milestones to --anim-ok, only "now" accent; alternate labels if crowded',
    'states': 'single current-state token; error transitions in --anim-danger; label offsets',
    'compare': 'panel headers (taken from a one-side group, else Before/After); left dims as right appears',
    'layers': 'layer names (from a one-layer group, else "Layer N"); bands rise 12 px bottom-up; response packet in --anim-ok',
    'chart': 'thresholds, readouts, axis titles, a baseline that does not exaggerate; downsample long series',
}


def main():
    ap = argparse.ArgumentParser(description='Scaffold an anim-slides fragment from a spec.')
    ap.add_argument('spec')
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--viewbox', nargs=2, type=int, metavar=('W', 'H'))
    ap.add_argument('--rendered-width', type=float)
    ap.add_argument('--min-text', type=float, default=18)
    ap.add_argument('--control', choices=['loop', 'step'])
    ap.add_argument('--no-check', action='store_true')
    args = ap.parse_args()

    S = validate(load_spec(args.spec), args)
    rw = args.rendered_width or S.W
    k = max(1.0, args.min_text * S.W / (18 * rw))
    F = {key: math.ceil(v * k * 2) / 2 for key, v in
         dict(title=26, head=26, lbl=22, note=22, sub=18, mono=18, edge=18).items()}
    if k > 1:
        warn(f'fonts scaled x{k:.2f} to stay >= {args.min_text:g}px at {rw:g}px wide; boxes may need resizing')
    fr = frame(S, F)
    scene = LAYOUTS[S.arch](S, F, fr[0], fr[1])
    T = Timing(S)
    anim = Anim()
    rid = build_anims(S, T, scene, anim)
    body = emit(S, args, F, scene, T, anim, rid, fr)

    words = ', '.join(n['label'] for n in S.nodes) or ', '.join(s['label'] for s in S.series)
    aria = escape(f'{S.title + ": " if S.title else ""}{S.arch} of {words}', quote=True)
    cyc = f1(T.end if T.loop else T.end + STEP)
    refine = ('<!-- scaffold: refine by hand -\n'
              f'  generated by scripts/scaffold_from_spec.py from {os.path.basename(args.spec)} '
              f'({S.arch}, {S.control}, {S.W}x{S.H}, rendered {rw:g}px)\n'
              f'  - {REFINE[S.arch]}\n'
              '  - node glyphs per kind are placeholders; check label fit, edge routing and overlaps\n'
              '  - aria-label: rewrite as one sentence that tells the story\n'
              '  - motion audit (references/motion-rules.md); render-phases.sh and LOOK at every PNG\n-->')
    html = [refine, '<style>', css(S, F, T, anim), '</style>',
            f'<div class="anim anim-{S.name}" data-anim="{S.name}" data-anim-cycle="{cyc}" '
            f'data-anim-control="{S.control}">',
            f'<svg viewBox="0 0 {S.W} {S.H}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" '
            f'role="img" aria-label="{aria}">']
    html += ['  ' + x for x in body]
    html.append('</svg>')
    if not T.loop:
        html.append(gsap_script(S, T, anim))
    html.append('</div>')
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(html) + '\n')
    print(f'wrote {args.output}: {S.arch}, {len(S.nodes)} nodes, {len(S.edges)} edges, '
          f'{len(S.phases)} phases, control {S.control}, viewBox {S.W}x{S.H}')
    if args.no_check:
        return
    checker = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'check_fragment.py')
    r = subprocess.run([sys.executable, checker, args.output, '--name', S.name, '--rendered-width', f'{rw:g}',
                        '--min-text', f'{args.min_text:g}'], capture_output=True, text=True)
    print(r.stdout, end='')
    if r.returncode:
        sys.exit('scaffold_from_spec: the output fails check_fragment.py (see above)')


if __name__ == '__main__':
    main()
