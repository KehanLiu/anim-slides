#!/usr/bin/env python3
"""Scaffold an anim-slides fragment from a spec (references/spec-format.md).

Usage:
  scaffold_from_spec.py SPEC.yaml|SPEC.json -o OUT.html
        [--viewbox W H] [--rendered-width PX] [--stage-width 1920] [--min-text PX]
        [--control once|loop|step] [--no-check]

  --viewbox         override the spec's size (viewBox width and height)
  --rendered-width  CSS px the SVG is shown at (default: the viewBox width); font sizes are
                    raised so every text meets --min-text there; the self-check uses it too
  --stage-width     width of the deck stage in CSS px (default 1920); sets the default --min-text
  --min-text        minimum rendered text size in px (default 18 * stage-width / 1920)
  --control         override the spec's control (once | loop | step); once and step re-time a loop
                    spec into a single pass of at most 10 s, loop re-times a once or step spec
  --no-check        do not run check_fragment.py on the output

The output is a skeleton that satisfies references/fragment-contract.md: a layout per archetype
(references/archetypes.md), phase timing from the spec and gated CSS keyframes, no script.
once: one pass that ends on the resting frame and holds it; step: the same file with
data-anim-control="step", which the host plays segment by segment between the data-anim-phases
marks; loop: an infinite cycle. data-anim-phases (always written) lists the start second of every
phase after the first, the hold's start last. Refine it by hand (see the scaffold comment at the
top of the output), then run render-phases.sh and look at every PNG.
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
    'top': {'name', 'archetype', 'title', 'size', 'control', 'cycle', 'nodes', 'edges', 'groups', 'lanes',
            'domain', 'illustrative',
            'phases', 'series', 'events'},
    'node': {'id', 'label', 'sub', 'kind', 'group', 'at', 'side', 'layer'},
    'edge': {'from', 'to', 'label', 'kind'},
    'group': {'id', 'label'},
    'phase': {'t', 'label', 'show', 'active', 'flow', 'note'},
    'series': {'id', 'label', 'points'},
    'event': {'id', 'at', 'label'},
}
ID_RE = re.compile(r'[a-z][a-z0-9]*(-[a-z0-9]+)*')
# name: CSS timing function
EASE = {'enter': 'cubic-bezier(0.16,1,0.3,1)', 'exit': 'cubic-bezier(0.3,0,1,1)',
        'move': 'cubic-bezier(0.45,0,0.55,1)', 'linear': 'linear'}
RESET = 0.4    # loop mode: the last seconds of the cycle fade back to the empty state
CYCLE = {'once': (4, 10, 8), 'loop': (8, 15, 12)}   # timing mode: (min s, max s, default s); step uses once
HOLD = {'once': 1.2, 'loop': 2.0}                   # seconds the final state is held before the end


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
                    raise MiniYAMLError(f'line {no}: expected ":" after key {k!r} in {{...}}; a plain '
                                        'value cannot contain a comma inside {...}: quote it '
                                        '(sub: "checked, warehoused")')
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
    spec_control = sp.get('control', 'once')
    need(spec_control in ('once', 'loop', 'step'), f'control {spec_control!r} must be once, loop or step')
    S.control = args.control or spec_control
    # timing mode: step is the once pass, played segment by segment by the host (data-anim-phases)
    S.mode = 'loop' if S.control == 'loop' else 'once'
    spec_mode = 'loop' if spec_control == 'loop' else 'once'
    retime = S.mode != spec_mode
    S.cycle = sp.get('cycle', CYCLE[spec_mode][2])
    if retime:          # --control override: the spec's timing was written for the other mode
        S.cycle = min(max(S.cycle if isinstance(S.cycle, (int, float)) else 0, CYCLE[S.mode][0]),
                      CYCLE[S.mode][1])
    lo, hi, _ = CYCLE[S.mode]
    need(isinstance(S.cycle, (int, float)) and lo <= S.cycle <= hi,
         f'cycle must be {lo}-{hi} s for control {S.control}'
         + (' (control defaults to once: one pass, then hold; write control: loop only for a kiosk, '
            'gallery or hero loop)' if 'control' not in sp and isinstance(S.cycle, (int, float))
            and S.cycle > hi else ''))
    size = args.viewbox or sp.get('size') or DEFAULT_SIZE[S.arch]
    need(isinstance(size, (list, tuple)) and len(size) == 2
         and all(isinstance(v, int) and v > 0 for v in size), 'size must be [W, H], positive integers')
    S.W, S.H = size if len(size) == 2 else (0, 0)
    S.title = str(sp['title']) if sp.get('title') else None
    hint(S.title, 48, 'title')

    need(sp.get('domain') is None or isinstance(sp.get('domain'), str), 'domain must be a string')  # pool metadata only
    S.illustrative = sp.get('illustrative', False)
    need(S.illustrative in (True, False), 'illustrative must be true or false')
    S.lanes = sp.get('lanes', False)
    need(S.lanes in (True, False), 'lanes must be true or false')
    if S.lanes and S.arch != 'graph':
        need(False, 'lanes: true is only allowed in graph')
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
            sd = n.get('side')
            need(isinstance(sd, str) and ID_RE.fullmatch(sd) and len(sd) <= 24,
                 f'{w}: side {sd!r} must be a kebab-case column name (left, right, or any other)')
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
    if S.lanes and not S.groups:
        warn('lanes: true without groups; drawing a plain graph')
        S.lanes = False
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
    elif retime:
        phases = retime_phases(S, [dict(p) for p in phases])
    S.phases = check_phases(S, phases, err)
    if err:
        die('\n  '.join(['invalid phases:'] + err))
    return S


def retime_phases(S, phases):
    """--control override between loop and once/step: fit the spec's phases into the new pass,
    ending with a hold phase. Phase seconds keep their proportions where the gaps allow."""
    lo, hi, _ = CYCLE[S.mode]
    hold = HOLD[S.mode]
    has_hold = phases[-1].get('label') == 'hold'
    body = phases[:-1] if has_hold and len(phases) > 1 else phases
    n = len(body)
    ts = [float(p.get('t') or 0) for p in body]
    h0 = float(phases[-1].get('t') or 0) if has_hold and len(phases) > 1 else (ts[-1] + hold if ts else hold)
    new = None
    if h0 > 0:
        k = (S.cycle - hold) / h0
        if S.mode == 'once':
            k = min(k, (hi - hold) / h0)
        new = [round(t * k, 2) for t in ts]
        if any(b - a < 0.8 - 1e-6 for a, b in zip(new, new[1:])):
            new = None
        else:
            h_t = round(h0 * k, 2)
    if new is None:
        st = max(0.8, math.floor((S.cycle - hold) / max(n, 1) * 10) / 10)
        new = [round(i * st, 2) for i in range(n)]
        h_t = round(n * st, 2)
    for p, t in zip(body, new):
        p['t'] = t
    end = dict(phases[-1]) if has_hold and len(phases) > 1 else {'label': 'hold'}
    end['t'] = h_t
    S.cycle = round(min(hi, max(lo, h_t + hold)), 1) if S.mode == 'once' else S.cycle
    warn(f'control overridden to {S.control}: phases re-timed into a {f1(S.cycle)} s pass with a hold')
    return body + [end]


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
        return [{'t': 0, 'label': 'setup'}, {'t': S.cycle - HOLD[S.mode], 'label': 'hold'}]
    n, hold, cyc = len(order), HOLD[S.mode], S.cycle
    top = CYCLE[S.mode][1]
    while True:
        st = round((cyc - hold) / n * 2) / 2
        if (n - 1) * st > cyc - hold - 0.8:
            st = math.floor((cyc - hold) / n * 10) / 10
        if st >= 0.8 or cyc >= top:
            break
        cyc += 1
    if st < 0.8:
        die(f'{n} nodes do not fit a {top} s {S.control} pass at 0.8 s per phase; split the spec or write phases')
    if cyc != S.cycle:
        warn(f'derived phases need cycle {cyc} s (was {S.cycle})')
        S.cycle = cyc
    phases, seen = [], set()
    for i, nid in enumerate(order):
        flow = [e['id'] for e in S.edges if e['to'] == nid and e['from'] in seen][:3]
        phases.append({'t': round(i * st, 2), 'label': nid,
                       'show': [nid], 'active': [nid], 'flow': flow})
        seen.add(nid)
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
        if p['label'] == 'hold' and p['active'] is None and out:
            p['active'] = list(out[-1]['active'])    # the hold keeps the final highlights (resting frame)
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
    ts = [p['t'] for p in out]
    if ts[0] != 0:
        err.append('the first phase must have t: 0')
    for a, b in zip(ts, ts[1:]):
        gap = round(b - a, 3)            # 11.2 - 10.4 is 0.7999... in floats
        least = 0.5 if S.mode == 'once' else 0.8   # a once pass is short: a 0.5 s beat still reads
        if gap < least:
            err.append(f'phase gap {a} -> {b} is under {least} s (or not increasing)')
        elif gap < 1:
            warn(f'phase gap {a} -> {b} is under 1 s')
    last_ok = S.cycle - (0.8 if S.mode == 'once' else 1)
    if ts[-1] > last_ok + 1e-6:
        err.append(f'phase t {ts[-1]} is after cycle - {f1(S.cycle - last_ok)} ({f1(last_ok)}): '
                   + ('the pass needs a final hold of 0.8 to 1.5 s' if S.mode == 'once' else
                      'the loop needs a hold before it restarts'))
    if out[-1]['label'] != 'hold':
        warn(f'the last phase is not labelled hold; the {"pass" if S.mode == "once" else "loop"} '
             'has no explicit hold')
    elif out[-1]['show'] or out[-1]['flow']:
        warn('the hold phase should have no show and no flow')
    if S.mode == 'once' and S.cycle - ts[-1] > 1.5 + 1e-6:
        warn(f'the final hold lasts {f1(S.cycle - ts[-1])} s (aim 0.8 to 1.5 s); shorten cycle to '
             f'{f1(ts[-1] + 1.2)}')
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


def wrap(text, fs, maxw, maxlines=2, mono=False):
    lines, cur = [], ''
    for word in text.split():
        cand = f'{cur} {word}'.strip()
        if cur and text_w(cand, fs, mono) > maxw:
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


def segs(c):
    """An edge is one cubic (a 4-tuple of points) or a list of cubics joined end to end."""
    return c if isinstance(c, list) else [c]


def path_d(c):
    s = segs(c)
    return f'M {pt(s[0][0])} ' + ' '.join(f'C {pt(q[1])} {pt(q[2])} {pt(q[3])}' for q in s)


def bez_mid(c):
    s = segs(c)
    if len(s) > 1:
        pts = sample(c)
        return pts[len(pts) // 2]
    c = s[0]
    return tuple((c[0][k] + 3 * c[1][k] + 3 * c[2][k] + c[3][k]) / 8 for k in (0, 1))


def arrow_d(c, size=11):
    """Small open chevron at the end of a wire."""
    c = segs(c)[-1]
    tip, back = c[3], c[2] if c[2] != c[3] else c[0]
    dx, dy = tip[0] - back[0], tip[1] - back[1]
    ln = math.hypot(dx, dy) or 1
    ux, uy = dx / ln, dy / ln
    bx, by = tip[0] - ux * size, tip[1] - uy * size
    return (f'M {pt((bx - uy * size * 0.6, by + ux * size * 0.6))} L {pt(tip)} '
            f'L {pt((bx + uy * size * 0.6, by - ux * size * 0.6))}')


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
# Every layout returns a scene: nodes {id: mark}, edges {edge id: cubic}, containers (columns,
# bands, lanes) and `back` markup drawn behind everything. A mark is the node's drawn shape (ring,
# diamond, dot or text row) as a box x, y, w, h with its centre cx, cy and radius r; wires attach
# to that box. Its text sits outside the shape: `lab` says where, `lbox` is the text's box and
# `foot` the union of both (what must stay clear of other nodes and inside the viewBox).
LABEL_GAP = 14      # ring edge to the first text line
WIRE_GAP = 6        # ring edge to the end of a wire


def frame(S, F):
    top = max(64, F['title'] + 38) if S.title else 24
    if S.illustrative and not S.title:
        top = max(top, 24 + F['mono'] + 16 + 18)     # the illustrative tag gets the top-right corner
    strip = max(56, F['note'] + 26)
    has_note = any(p['note'] for p in S.phases)
    bottom = S.H - strip - 16 if has_note else S.H - 24
    return top, bottom, strip, has_note


def label_lines(n, F, maxw, maxl=2):
    """A node's text as (text, role) lines: the label wrapped to maxl lines, the sub (mono) to 2."""
    out = [(t, 'lbl') for t in wrap(n['label'], F['lbl'], maxw, maxl)]
    if n['sub']:
        out += [(t, 'sub') for t in wrap(n['sub'], F['sub'], maxw, 2, True)]
    return out


def line_w(t, role, F):
    return text_w(t, F[role], role in ('sub', 'mono', 'edge'))


def block_w(lines, F):
    return max((line_w(t, r, F) for t, r in lines), default=0)


def need_w(S, F, subs=True):
    """Narrowest text column in which every label wraps to at most two lines (and every sub)."""
    need = 60
    for n in S.nodes:
        need = max(need, max((text_w(x, F['lbl']) for x in n['label'].split()), default=0),
                   text_w(n['label'], F['lbl']) * 0.55)
        if n['sub'] and subs:
            need = max(need, max((text_w(x, F['sub'], True) for x in n['sub'].split()), default=0),
                       text_w(n['sub'], F['sub'], True) * 0.55)
    return need


def mark(F, n, cx, cy, shape=None):
    """The drawn shape of a node: a ring (r 32-44 at a 1920 stage), a thin diamond for decisions."""
    shape = shape or ('diamond' if n['kind'] == 'decision' else 'ring')
    r = F['ring'] * (1.3 if shape == 'diamond' else 1) if shape != 'dot' else F['dot']
    return dict(x=cx - r, y=cy - r, w=2 * r, h=2 * r, cx=cx, cy=cy, r=r, shape=shape)


def union(a, b):
    x0, y0 = min(a['x'], b['x']), min(a['y'], b['y'])
    return dict(x=x0, y=y0, w=max(a['x'] + a['w'], b['x'] + b['w']) - x0,
                h=max(a['y'] + a['h'], b['y'] + b['h']) - y0)


def put_label(b, lines, side, F, gap=LABEL_GAP):
    """Place a node's text block outside its mark: below, above, left or right."""
    th, bw = text_h(lines, F), block_w(lines, F)
    if side == 'below':
        x, y, anchor, bx = b['cx'], b['y'] + b['h'] + gap, 'middle', b['cx'] - bw / 2
    elif side == 'above':
        x, y, anchor, bx = b['cx'], b['y'] - gap - th, 'middle', b['cx'] - bw / 2
    elif side == 'right':
        x, y, anchor, bx = b['x'] + b['w'] + gap, b['cy'] - th / 2, 'start', b['x'] + b['w'] + gap
    else:
        x, y, anchor, bx = b['x'] - gap, b['cy'] - th / 2, 'end', b['x'] - gap - bw
    b['lab'] = dict(lines=lines, x=x, y=y, anchor=anchor, side=side)
    b['lbox'] = dict(x=bx, y=y, w=bw, h=th)
    b['foot'] = union(b, b['lbox'])
    return b


def foot(b):
    return b.get('foot', b)


def ring_port(b, side, dy):
    """x where a wire leaving at height cy + dy meets the side (+1 right, -1 left) of a mark."""
    if b.get('shape') == 'diamond':
        return b['cx'] + side * (b['r'] - abs(dy)) + side * WIRE_GAP
    if b.get('shape') in ('ring', 'dot'):
        return b['cx'] + side * (math.sqrt(max(0.0, b['r'] ** 2 - dy * dy)) + WIRE_GAP)
    return b['x'] + (b['w'] if side > 0 else 0)


def quarter(p, q, horizontal_first):
    """A rounded corner from p to q as one cubic."""
    k = 0.5523
    if horizontal_first:
        return cubic(p, (p[0] + (q[0] - p[0]) * k, p[1]), (q[0], q[1] - (q[1] - p[1]) * k), q)
    return cubic(p, (p[0], p[1] + (q[1] - p[1]) * k), (q[0] - (q[0] - p[0]) * k, q[1]), q)


def top_arc(a, b, depth):
    """Arc from the top of mark a to the top of mark b, bowing up by about 0.75 * depth."""
    p0, p3 = (a['cx'], a['y'] - WIRE_GAP), (b['cx'], b['y'] - WIRE_GAP)
    yc = min(p0[1], p3[1]) - depth
    return cubic(p0, (p0[0], yc), (p3[0], yc), p3)


def bottom_arc(a, b, depth):
    p0, p3 = (a['cx'], a['y'] + a['h'] + WIRE_GAP), (b['cx'], b['y'] + b['h'] + WIRE_GAP)
    yc = max(p0[1], p3[1]) + depth
    return cubic(p0, (p0[0], yc), (p3[0], yc), p3)


def ring_route(a, b):
    """Cubic between the facing sides of two marks."""
    (ax, ay), (bx, by) = (a['cx'], a['cy']), (b['cx'], b['cy'])
    if abs(bx - ax) >= abs(by - ay):
        s = 1 if bx > ax else -1
        p0, p3 = (ring_port(a, s, 0), ay), (ring_port(b, -s, 0), by)
        kk = max(40, min(120, abs(p3[0] - p0[0]) / 2))
        return cubic(p0, (p0[0] + s * kk, p0[1]), (p3[0] - s * kk, p3[1]), p3)
    s = 1 if by > ay else -1
    p0, p3 = (ax, ay + s * (a['h'] / 2 + WIRE_GAP)), (bx, by - s * (b['h'] / 2 + WIRE_GAP))
    kk = max(30, min(100, abs(p3[1] - p0[1]) / 2))
    return cubic(p0, (p0[0], p0[1] + s * kk), (p3[0], p3[1] - s * kk), p3)


def layout_pipeline(S, F, top, bottom):
    """Rings on one thin line, labels below; skip and back edges arc over the top."""
    n, W = len(S.nodes), S.W
    pitch = min(380, (W - 80) / n)
    need = max(need_w(S, F), max(text_w(nd['sub'], F['sub'], True) for nd in S.nodes if nd['sub'])
               if any(nd['sub'] for nd in S.nodes) else 0)
    m = math.ceil(n / 2)
    pitch2 = min(380, (W - 80 - 140) / m)
    if n >= 4 and need > pitch - 28 and pitch2 > pitch * 1.15:   # wrap only when two rows really give room
        return layout_pipeline_snake(S, F, top, bottom, need)
    if need > pitch - 28:
        warn(f'pipeline: labels need a {need:.0f} px column, one row gives {pitch - 28:.0f}; widen --viewbox '
             f'(about {math.ceil(n * (need + 28) + 80)} wide) or shorten labels')
    idx = {nd['id']: i for i, nd in enumerate(S.nodes)}
    arcs = [e for e in S.edges if idx[e['to']] != idx[e['from']] + 1]
    labs = {nd['id']: label_lines(nd, F, pitch - 28) for nd in S.nodes}
    th = max(text_h(v, F) for v in labs.values())
    hr = max(mark(F, nd, 0, 0)['r'] for nd in S.nodes)
    up = (max(56, 40 + 16 * (len(arcs) - 1)) + (F['edge'] + 8 if any(e['label'] for e in arcs) else 0)) if arcs else 0
    fig = up + 2 * hr + LABEL_GAP + th
    cy = top + max(0, (bottom - top - fig) / 2) + up + hr
    x0 = W / 2 - (n - 1) * pitch / 2
    nodes = {nd['id']: put_label(mark(F, nd, x0 + i * pitch, cy), labs[nd['id']], 'below', F)
             for i, nd in enumerate(S.nodes)}
    edges = {}
    depth = 40
    for e in sorted(S.edges, key=lambda e: abs(idx[e['to']] - idx[e['from']])):
        a, b = nodes[e['from']], nodes[e['to']]
        if e not in arcs:
            edges[e['id']] = straight((ring_port(a, 1, 0), cy), (ring_port(b, -1, 0), cy))
        else:
            edges[e['id']] = top_arc(a, b, depth / 0.75)
            depth += 16
    return dict(nodes=nodes, edges=edges)


def layout_pipeline_snake(S, F, top, bottom, need):
    """Two rows: the first left to right, the second right to left under it, joined by a wrap
    wire that bends round the right end (and a return wire round the left end, if any)."""
    n, W = len(S.nodes), S.W
    m = math.ceil(n / 2)
    idx = {nd['id']: i for i, nd in enumerate(S.nodes)}
    back_l = [e for e in S.edges if col_of(idx[e['from']], m) == col_of(idx[e['to']], m) == 0
              and idx[e['from']] // m != idx[e['to']] // m]
    res_r, res_l = 64, 64 if back_l else 0
    pitch = min(380, (W - 80 - res_r - res_l) / m)
    if need > pitch - 28:
        warn(f'pipeline: {n} nodes need a {need:.0f} px text column but two rows only give {pitch - 28:.0f}; '
             f'widen --viewbox (about {math.ceil(m * (need + 28) + 80 + res_r + res_l)} wide) or split the spec')
    labs = {nd['id']: label_lines(nd, F, pitch - 28) for nd in S.nodes}
    th = max(text_h(v, F) for v in labs.values())
    hr = max(mark(F, nd, 0, 0)['r'] for nd in S.nodes)
    arcs = [e for e in S.edges if e not in back_l and not (idx[e['to']] == idx[e['from']] + 1)]
    up = 40 if arcs else 0
    rgap = 2 * hr + LABEL_GAP + th + 48
    fig = up + rgap + 2 * hr + LABEL_GAP + th
    y0 = top + max(0, (bottom - top - fig) / 2) + up + hr
    left = (W - m * pitch - res_r - res_l) / 2 + res_l
    xs = [left + pitch / 2 + c * pitch for c in range(m)]
    nodes = {}
    for i, nd in enumerate(S.nodes):
        r, c = divmod(i, m)
        c = c if r == 0 else m - 1 - c
        b = mark(F, nd, xs[c], y0 + r * rgap)
        b.update(col=c, lane=r)
        nodes[nd['id']] = put_label(b, labs[nd['id']], 'below', F)
    xr, xl, rad = xs[-1] + pitch / 2 + 20, xs[0] - pitch / 2 - 20, 32
    edges = {}
    for e in S.edges:
        a, b = nodes[e['from']], nodes[e['to']]
        ay, by = a['cy'], b['cy']
        if a['lane'] == b['lane'] and abs(a['col'] - b['col']) == 1:
            s = 1 if b['cx'] > a['cx'] else -1
            edges[e['id']] = straight((ring_port(a, s, 0), ay), (ring_port(b, -s, 0), by))
        elif a['lane'] != b['lane'] and a['col'] == b['col'] in (0, m - 1) and (a['col'] == m - 1 or e in back_l):
            s = 1 if a['col'] == m - 1 and e not in back_l else -1     # round the right (or left) end
            x = xr if s > 0 else xl
            dy = 1 if by > ay else -1
            p0, p3 = (ring_port(a, s, 0), ay), (ring_port(b, s, 0), by)
            c1, c2 = (x - s * rad, ay), (x - s * rad, by)
            edges[e['id']] = [straight(p0, c1), quarter(c1, (x, ay + dy * rad), True),
                              straight((x, ay + dy * rad), (x, by - dy * rad)),
                              quarter((x, by - dy * rad), c2, False), straight(c2, p3)]
        elif a['lane'] == b['lane']:
            edges[e['id']] = top_arc(a, b, 40)
        else:
            edges[e['id']] = ring_route(a, b)
    return dict(nodes=nodes, edges=edges)


def col_of(i, m):
    r, c = divmod(i, m)
    return c if r == 0 else m - 1 - c


def ranks(S, backs=None, pull=False):
    """Longest-path rank of every node over the edges that are not back edges (DFS in list order).
    pull: a source moves right to sit one rank before its nearest successor."""
    order = [n['id'] for n in S.nodes]
    out = {i: [e['to'] for e in S.edges if e['from'] == i] for i in order}
    state, bk = {}, set() if backs is None else backs

    def dfs(u):
        state[u] = 1
        for v in out[u]:
            if state.get(v) == 1:
                bk.add(f'{u}>{v}')
            elif v not in state:
                dfs(v)
        state[u] = 2
    for u in order:
        if u not in state:
            dfs(u)
    rank = {i: 0 for i in order}
    for _ in order:
        for e in S.edges:
            if e['id'] not in bk:
                rank[e['to']] = max(rank[e['to']], rank[e['from']] + 1)
    if pull:
        fwd = [e for e in S.edges if e['id'] not in bk]
        for u in order:
            succ = [rank[e['to']] for e in fwd if e['from'] == u]
            if succ and not any(e['to'] == u for e in fwd):
                rank[u] = max(rank[u], min(succ) - 1)
    return rank


# graph squeeze levels, loosest first: spacing and text columns shrink, fonts never do
GRAPH_FIT = (dict(margin=40, gap=60, vgap=30, gpad=20, ghead=44, clear=22, nw=240),
             dict(margin=32, gap=44, vgap=22, gpad=16, ghead=40, clear=18, nw=210),
             dict(margin=24, gap=32, vgap=14, gpad=12, ghead=36, clear=14, nw=180))


def layer_crossings(layers, ladj):
    total = 0
    for r in range(len(layers) - 1):
        p = {it: i for i, it in enumerate(layers[r])}
        q = {it: i for i, it in enumerate(layers[r + 1])}
        es = [(p[a], q[b]) for a, b in ladj if a in p and b in q]
        total += sum(1 for i in range(len(es)) for j in range(i + 1, len(es))
                     if (es[i][0] - es[j][0]) * (es[i][1] - es[j][1]) < 0)
    return total


def layout_graph(S, F, top, bottom, level=0, mode='below'):
    """Layered left to right (Sugiyama): ranks by longest path, edges that skip ranks get a
    waypoint in every column they pass, columns ordered by barycenter sweeps (spec order breaks
    ties, group members kept together), rows placed by a constrained relaxation that keeps nodes
    out of foreign group brackets. Each node is a ring with its text below, so a node reaches r
    above its centre and r + text below. Back edges: a reverse pair runs as a twin wire, longer
    ones arc below (or above) everything they span. mode 'side' (the fallback when the text
    below does not fit the height) puts the text right of the ring and wires leave past it."""
    side = mode == 'side'
    if S.lanes:
        return layout_lanes(S, F, top, bottom)
    lg = LABEL_GAP
    if mode == 'small':                               # last resort before giving up: smaller rings
        F, lg = dict(F, ring=round(F['ring'] * 0.72)), 10
    P = GRAPH_FIT[level]
    backs = set()
    rank = ranks(S, backs, pull=True)
    R = max(rank.values()) + 1
    idx = {n['id']: i for i, n in enumerate(S.nodes)}
    fwd = [e for e in S.edges if e['id'] not in backs]
    pair = {e['id'] for e in S.edges if e['id'] in backs and f'{e["to"]}>{e["from"]}' in S.edge
            and abs(rank[e['from']] - rank[e['to']]) == 1}
    arcs = [e for e in S.edges if e['id'] in backs and e['id'] not in pair]
    grp = {n['id']: n.get('group') for n in S.nodes}
    span = {}
    for n in S.nodes:
        if n.get('group'):
            a, b = span.get(n['group'], (R, -1))
            span[n['group']] = (min(a, rank[n['id']]), max(b, rank[n['id']]))

    # ---- layered graph: dummies for every rank an edge skips
    layers = [[] for _ in range(R)]
    for n in sorted(S.nodes, key=lambda n: idx[n['id']]):
        layers[rank[n['id']]].append(n['id'])
    chain, ladj, tie = {}, [], {n['id']: float(idx[n['id']]) for n in S.nodes}
    for k, e in enumerate(fwd):
        u, v = e['from'], e['to']
        seq = [u]
        for r in range(rank[u] + 1, rank[v]):
            d = ('~', e['id'], r)
            g = grp[u] if grp[u] and span[grp[u]][0] <= r <= span[grp[u]][1] else \
                grp[v] if grp[v] and span[grp[v]][0] <= r <= span[grp[v]][1] else None
            grp[d] = g
            tie[d] = (idx[u] + idx[v]) / 2 + k * 1e-3
            layers[r].append(d)
            seq.append(d)
        seq.append(v)
        chain[e['id']] = seq
        ladj += list(zip(seq, seq[1:]))
    nb_l = {it: [] for L in layers for it in L}
    nb_r = {it: [] for L in layers for it in L}
    for a, b in ladj:
        nb_r[a].append(b)
        nb_l[b].append(a)

    def sort_layer(r, ref):
        pos = {it: i for i, it in enumerate(layers[ref])} if ref is not None else {}
        cur = {it: i for i, it in enumerate(layers[r])}
        nbs = nb_l if ref is not None and ref < r else nb_r
        bary = {}
        for it in layers[r]:
            ps = [pos[x] for x in nbs[it] if x in pos]
            bary[it] = sum(ps) / len(ps) if ps else cur[it] * max(1, len(pos)) / max(1, len(cur))
        blocks = {}
        for it in layers[r]:
            blocks.setdefault(grp[it] or ('solo', it), []).append(it)
        ordered = sorted(blocks.values(), key=lambda m: (sum(bary[i] for i in m) / len(m), min(tie[i] for i in m)))
        layers[r] = [i for m in ordered for i in sorted(m, key=lambda i: (bary[i], tie[i]))]

    for r in range(R):
        sort_layer(r, None)
    for r in range(1, R):
        sort_layer(r, r - 1)
    best, best_c = [list(L) for L in layers], layer_crossings(layers, ladj)
    for _ in range(6):
        for r in range(R - 2, -1, -1):
            sort_layer(r, r + 1)
        for r in range(1, R):
            sort_layer(r, r - 1)
        c = layer_crossings(layers, ladj)
        if c < best_c:
            best, best_c = [list(L) for L in layers], c
        if best_c == 0:
            break
    layers = best

    # ---- text columns and footprints (x)
    tw_need = need_w(S, F, subs=False)                # floor: labels wrap to two lines; a long sub only warns
    avail = S.W - 2 * P['margin']
    nw = max(tw_need, min(P['nw'], (avail - P['gap'] * (R - 1)) / R))
    proto = {n['id']: mark(F, n, 0, 0) for n in S.nodes}
    if side:
        hr = max(b['r'] for b in proto.values())
        nw = max(tw_need, min(P['nw'], (avail - P['gap'] * (R - 1)) / R - 2 * hr - lg))
    labs = {n['id']: label_lines(n, F, nw) for n in S.nodes}
    if side:
        size = {i: (proto[i]['w'] + lg + block_w(labs[i], F), max(proto[i]['r'], text_h(labs[i], F) / 2),
                    max(proto[i]['r'], text_h(labs[i], F) / 2)) for i in proto}
    else:
        size = {i: (max(proto[i]['w'], block_w(labs[i], F)), proto[i]['r'],
                    proto[i]['r'] + lg + text_h(labs[i], F)) for i in proto}
    cw = [max([size[i][0] for i in L if not isinstance(i, tuple)] or [0]) for L in layers]
    gap = (avail - sum(cw)) / (R - 1) if R > 1 else 0
    gap = max(P['gap'], min(gap, 2.2 * nw))
    total = sum(cw) + gap * (R - 1)
    xl, x = [], (S.W - total) / 2
    for r in range(R):
        xl.append(x)
        x += cw[r] + gap
    cx = [xl[r] + cw[r] / 2 for r in range(R)]

    # ---- group headers (label may wrap once the bracket width is known)
    head = {}
    for g in S.groups:
        ms = [n['id'] for n in S.nodes if n.get('group') == g['id']]
        if not ms:
            continue
        x0 = min(cx[rank[i]] - size[i][0] / 2 for i in ms) - P['gpad']
        x1 = max(cx[rank[i]] + size[i][0] / 2 for i in ms) + P['gpad']
        nl = len(group_label_lines(g, F, x1 - x0))
        head[g['id']] = max(P['ghead'], 14 + F['sub'] * 1.3 + 10) + (nl - 1) * F['sub'] * 1.25

    # ---- rows (y): ht = extent above the centre, hb = below it (ring + text)
    lo, hi = top + (40 if arcs else 0), bottom
    ht = {it: (size[it][1] if not isinstance(it, tuple) else 0) for L in layers for it in L}
    hb = {it: (size[it][2] if not isinstance(it, tuple) else 0) for L in layers for it in L}

    def gap_of(a, b):
        da, db = isinstance(a, tuple), isinstance(b, tuple)
        base = P['clear'] if da and db else P['clear'] + 8 if da or db else P['vgap']
        ga, gb = grp[a], grp[b]
        if ga != gb:
            base = max(base, (P['gpad'] if ga else 0) + (head[gb] if gb else 0) + (12 if not (da or db) else 8))
        return hb[a] + ht[b] + base

    y = {}
    for L in layers:                                  # start: each column stacked round the middle
        gaps = [gap_of(a, b) for a, b in zip(L, L[1:])]
        yy = (lo + hi) / 2 - sum(gaps) / 2
        for k, it in enumerate(L):
            y[it] = yy
            yy += gaps[k] if k < len(gaps) else 0
    col = {it: r for r, L in enumerate(layers) for it in L}
    lb = {it: lo + ht[it] + (head[grp[it]] if grp[it] else 0) for it in y}
    ub = {it: hi - hb[it] - (P['gpad'] if grp[it] else 0) for it in y}
    members = {g: [it for it in y if grp[it] == g] for g in head}
    gix = {g['id']: k for k, g in enumerate(S.groups)}
    gx = {}                                           # group bracket x range (fixed by the columns)
    for g in head:
        ns = [i for i in members[g] if not isinstance(i, tuple)]
        gx[g] = (min(cx[rank[i]] - size[i][0] / 2 for i in ns) - P['gpad'],
                 max(cx[rank[i]] + size[i][0] / 2 for i in ns) + P['gpad'])
    order_cons = [(a, b, gap_of(a, b)) for L in layers for a, b in zip(L, L[1:])]

    def extent(it):
        r = col[it]
        if isinstance(it, tuple):
            return xl[r], xl[r] + cw[r]
        return cx[r] - size[it][0] / 2, cx[r] + size[it][0] / 2

    def sides():
        """(item, group, above): every foreign item whose column crosses a group's span."""
        out = []
        for r, L in enumerate(layers):
            for k, it in enumerate(L):
                ix0, ix1 = extent(it)
                for g in head:
                    if g == grp[it] or ix1 <= gx[g][0] or ix0 >= gx[g][1]:
                        continue
                    here = [j for j, o in enumerate(L) if grp[o] == g]
                    if here:
                        above = k < here[0]
                    else:
                        ms = members[g]
                        c = (min(y[m] - ht[m] for m in ms) + max(y[m] + hb[m] for m in ms)) / 2
                        above = y[it] < c - 1 if abs(y[it] - c) > 1 else \
                            (grp[it] is not None and gix[grp[it]] < gix[g])
                    out.append((it, g, above))
        return out

    def excl_cons(sd):
        out = []
        for it, g, above in sd:
            o, cl = grp[it], 10 if isinstance(it, tuple) else 12
            for m in members[g]:
                if above:
                    out.append((it, m, hb[it] + cl + (P['gpad'] if o else 0) + head[g] + ht[m]))
                else:
                    out.append((m, it, hb[m] + P['gpad'] + cl + (head[o] if o else 0) + ht[it]))
        return out

    def project(cons):
        for a, b, g in cons:
            v = g - (y[b] - y[a])
            if v > 1e-6:
                na = max(lb[a], y[a] - v / 2)
                nb = min(ub[b], y[b] + v - (y[a] - na))
                if nb - na < g:
                    na = max(lb[a], nb - g)
                y[a], y[b] = na, nb

    def solve(cons, iters=120):
        for _ in range(iters):                        # relax toward neighbours, then re-impose
            for it in y:
                ns = nb_l[it] + nb_r[it]
                if ns:
                    y[it] = 0.5 * y[it] + 0.5 * sum(y[x] for x in ns) / len(ns)
                y[it] = min(max(y[it], lb[it]), ub[it])
            for _ in range(4):
                project(cons)
        for _ in range(60):
            project(cons)
        return max([g - (y[b] - y[a]) for a, b, g in cons] + [0])

    solve(order_cons, 60)
    for _ in range(2):
        cons = order_cons + excl_cons(sides())
        solve(cons)
    conflicts = [f'{a if isinstance(a, str) else "wire " + a[1]} / {b if isinstance(b, str) else "wire " + b[1]}'
                 for a, b, g in cons if g - (y[b] - y[a]) > 1]

    def boxes():
        out = {}
        for g, ms in members.items():
            out[g] = dict(x=gx[g][0], y=min(y[i] - ht[i] for i in ms) - head[g], w=gx[g][1] - gx[g][0])
            out[g]['h'] = max(y[i] + hb[i] for i in ms) + P['gpad'] - out[g]['y']
        return out

    # centre the drawing vertically in the band
    gb = boxes()
    ys0 = [y[i] - ht[i] for i in y] + [b['y'] for b in gb.values()]
    ys1 = [y[i] + hb[i] for i in y] + [b['y'] + b['h'] for b in gb.values()]
    dy = (lo + hi) / 2 - (min(ys0) + max(ys1)) / 2
    if min(ys0) + dy >= top - 0.5 and max(ys1) + dy <= hi + 0.5:
        for i in y:
            y[i] += dy
        for b in gb.values():
            b['y'] += dy

    nodes = {}
    for n in S.nodes:
        i = n['id']
        if side:
            nodes[i] = put_label(mark(F, n, cx[rank[i]] - size[i][0] / 2 + proto[i]['r'], y[i]), labs[i], 'right', F, lg)
        else:
            nodes[i] = put_label(mark(F, n, cx[rank[i]], y[i]), labs[i], 'below', F, lg)

    def out_port(i, dy_):
        b = nodes[i]
        return b['foot']['x'] + b['foot']['w'] + WIRE_GAP if side else ring_port(b, 1, dy_)

    # ---- routing
    def spread(i, lst):
        """lst: [(key y, edge id)] on one side of node i -> {edge id: dy}"""
        lst.sort()
        b = nodes[i]
        n_ = len(lst)
        if n_ < 2:
            return {eid: 0.0 for _, eid in lst}
        sp = min(14 if b['shape'] != 'diamond' else 10, (b['r'] * (1.2 if b['shape'] != 'diamond' else 0.5)) / (n_ - 1))
        sp = max(sp, 6)
        return {eid: (k - (n_ - 1) / 2) * sp for k, (_, eid) in enumerate(lst)}

    outs, ins = {}, {}
    for e in fwd:
        seq = chain[e['id']]
        outs.setdefault(e['from'], []).append((y[seq[1]], tie.get(seq[1], 0), e['id']))
        ins.setdefault(e['to'], []).append((y[seq[-2]], tie.get(seq[-2], 0), e['id']))
    po, pi = {}, {}
    for i, lst in outs.items():
        po.update(spread(i, [((a, t), eid) for a, t, eid in lst]))
    for i, lst in ins.items():
        pi.update(spread(i, [((a, t), eid) for a, t, eid in lst]))

    def s_curve(p, q):
        k = max(20, (q[0] - p[0]) * 0.5)
        return cubic(p, (p[0] + k, p[1]), (q[0] - k, q[1]), q)

    edges = {}
    for e in fwd:
        seq = chain[e['id']]
        tw = 7 if f'{e["to"]}>{e["from"]}' in pair else 0
        p = (out_port(e['from'], po[e['id']] - tw), y[e['from']] + po[e['id']] - tw)
        segs_ = []
        for d in seq[1:-1]:
            r = d[2]
            a, b = (xl[r], y[d] - tw), (xl[r] + cw[r], y[d] - tw)
            segs_.append(s_curve(p, a))
            segs_.append(straight(a, b))
            p = b
        q = (ring_port(nodes[e['to']], -1, pi[e['id']] - tw), y[e['to']] + pi[e['id']] - tw)
        segs_.append(s_curve(p, q))
        edges[e['id']] = segs_ if len(segs_) > 1 else segs_[0]
        if tw:
            rev = [tuple((pt_[0], pt_[1] + 2 * tw) for pt_ in reversed(c)) for c in reversed(segs(edges[e['id']]))]
            edges[f'{e["to"]}>{e["from"]}'] = rev if len(rev) > 1 else rev[0]
    for e in arcs:                                    # back edges: over the top of everything they span
        a, b = nodes[e['from']], nodes[e['to']]
        x0e, x1e = sorted((a['cx'], b['cx']))
        sp_ = [foot(o) for o in nodes.values() if foot(o)['x'] < x1e and foot(o)['x'] + foot(o)['w'] > x0e]
        sp_ += [bx for gid, bx in gb.items() if bx['x'] < x1e and bx['x'] + bx['w'] > x0e]
        hi_ = min(o['y'] for o in sp_) - 24
        if hi_ >= top - 0.5:
            edges[e['id']] = top_arc(a, b, max(40, (min(a['y'], b['y']) - hi_) / 0.75))
        else:
            edges[e['id']] = loop_under(a, b, max(o['y'] + o['h'] for o in sp_) + 24)
    scene = dict(nodes=nodes, edges=edges, gboxes=gb, level=level, conflicts=conflicts, mode=mode)
    scene['labels'] = place_edge_labels(S, F, scene)
    return scene


def loop_under(a, b, yl, rad=28):
    """Back wire that leaves mark a on its far side, drops below everything to yl, runs across
    and climbs into mark b from b's far side: a rounded rectangle under the text blocks."""
    s = 1 if b['cx'] > a['cx'] else -1
    ext = lambda m: max(m['r'], m.get('lbox', {'w': 0})['w'] / 2) + 24   # noqa: E731
    xa, xb = a['cx'] - s * ext(a), b['cx'] + s * ext(b)
    p0, p3 = (ring_port(a, -s, 0), a['cy']), (ring_port(b, s, 0), b['cy'])
    return [straight(p0, (xa + s * rad, a['cy'])), quarter((xa + s * rad, a['cy']), (xa, a['cy'] + rad), True),
            straight((xa, a['cy'] + rad), (xa, yl - rad)), quarter((xa, yl - rad), (xa + s * rad, yl), False),
            straight((xa + s * rad, yl), (xb - s * rad, yl)), quarter((xb - s * rad, yl), (xb, yl - rad), True),
            straight((xb, yl - rad), (xb, b['cy'] + rad)), quarter((xb, b['cy'] + rad), (xb - s * rad, b['cy']), False),
            straight((xb - s * rad, b['cy']), p3)]


def sample(c, n=16):
    """Points along a cubic or a list of cubics, n per segment."""
    pts = []
    for q in segs(c):
        for k in range(1 if pts else 0, n + 1):
            t = k / n
            mt = 1 - t
            pts.append(tuple(mt ** 3 * q[0][j] + 3 * mt * mt * t * q[1][j] + 3 * mt * t * t * q[2][j]
                             + t ** 3 * q[3][j] for j in (0, 1)))
    return pts


def seg_cross(p1, p2, p3, p4):
    def o(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    d1, d2, d3, d4 = o(p3, p4, p1), o(p3, p4, p2), o(p1, p2, p3), o(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and 0 not in (d1, d2, d3, d4)


def poly_hits_box(pts, b, pad=0):
    x0, y0, x1, y1 = b['x'] - pad, b['y'] - pad, b['x'] + b['w'] + pad, b['y'] + b['h'] + pad
    for p, q in zip(pts, pts[1:]):
        for k in range(5):
            t = k / 4
            x, y = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
            if x0 < x < x1 and y0 < y < y1:
                return True
    return False


def edge_label_box(S, F, e, at):
    tw = text_w(e['label'], F['edge'], True) + 12
    return dict(x=at[0] - tw / 2, y=at[1] - F['edge'] * 0.625, w=tw, h=F['edge'] * 1.25)


def place_edge_labels(S, F, scene):
    """Label centre per labelled edge: the first point along the wire (middle first) where the
    label box touches no other wire, no node and no earlier label."""
    pts = {e['id']: sample(scene['edges'][e['id']]) for e in S.edges}
    out, taken, bad = {}, [], []
    for e in S.edges:
        if not e['label']:
            continue
        P_ = pts[e['id']]
        best = None
        cands = []
        for f in (0.5, 0.42, 0.58, 0.34, 0.66, 0.26, 0.74, 0.18, 0.82):
            k = round(f * (len(P_) - 1))
            p0, p1 = P_[max(0, k - 1)], P_[min(len(P_) - 1, k + 1)]
            ln = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) or 1
            nx, ny = -(p1[1] - p0[1]) / ln, (p1[0] - p0[0]) / ln       # beside the wire, not on it
            tw = text_w(e['label'], F['edge'], True) + 12
            d = abs(nx) * tw / 2 + abs(ny) * F['edge'] * 0.625 + 6
            for sg in ((-1, 1) if ny <= 0 else (1, -1)):
                cands.append((P_[k][0] + sg * nx * d, P_[k][1] + sg * ny * d))
        for at in cands:
            box = edge_label_box(S, F, e, at)
            hits = sum(1 for o in S.edges if poly_hits_box(pts[o['id']], box, 2))
            hits += sum(1 for b in scene['nodes'].values() if overlaps(box, b, 4)
                        or ('lbox' in b and overlaps(box, b['lbox'], 4)))
            hits += sum(1 for b in taken if overlaps(box, b, 4))
            if best is None or hits < best[0]:
                best = (hits, at, box)
            if not hits:
                break
        out[e['id']] = best[1]
        taken.append(best[2])
        if best[0]:
            bad.append(e['id'])
    scene['label_bad'] = bad
    return out


def edge_report(S, scene):
    """(crossings, edges through nodes or their text) of the drawn wires."""
    pts = {e['id']: sample(scene['edges'][e['id']], 24) for e in S.edges}
    cross = []
    es = S.edges
    for i in range(len(es)):
        for j in range(i + 1, len(es)):
            a, b = es[i], es[j]
            if {a['from'], a['to']} & {b['from'], b['to']}:
                continue
            A, B = pts[a['id']], pts[b['id']]
            if any(seg_cross(A[k], A[k + 1], B[m], B[m + 1]) for k in range(len(A) - 1) for m in range(len(B) - 1)):
                cross.append(f'{a["id"]} x {b["id"]}')
    through = []
    for e in es:
        for nid, b in scene['nodes'].items():
            if nid in (e['from'], e['to']):
                continue
            if poly_hits_box(pts[e['id']], b, -2) or ('lbox' in b and poly_hits_box(pts[e['id']], b['lbox'], -2)):
                through.append(f'{e["id"]} through {nid}')
    return cross, through


def group_label_lines(g, F, w):
    return wrap(g['label'], F['sub'], w - 32, 3, True)


def group_box(S, nodes, gid, F=None):
    """Box round a group's members (rings and text); with F the top grows so a wrapped label fits."""
    bs = [foot(nodes[n['id']]) for n in S.nodes if n.get('group') == gid]
    x, y = min(b['x'] for b in bs) - 20, min(b['y'] for b in bs) - 44
    box = dict(x=x, y=y, w=max(b['x'] + b['w'] for b in bs) + 20 - x, h=max(b['y'] + b['h'] for b in bs) + 16 - y)
    if F:
        extra = (len(group_label_lines(S.group[gid], F, box['w'])) - 1) * F['sub'] * 1.25
        box['y'] -= extra
        box['h'] += extra
    return box


def overlaps(a, b, pad=0):
    return (a['x'] < b['x'] + b['w'] + pad and a['x'] + a['w'] + pad > b['x']
            and a['y'] < b['y'] + b['h'] + pad and a['y'] + a['h'] + pad > b['y'])


def put_label_low(b, lines, F, gap=LABEL_GAP):
    """Text to the right of the ring, hanging just under the centre line, so a wire that leaves
    the ring sideways runs over it (a label on a line)."""
    th, bw = text_h(lines, F), block_w(lines, F)
    x, y = b['x'] + b['w'] + gap, b['cy'] + 8
    b['lab'] = dict(lines=lines, x=x, y=y, anchor='start', side='right')
    b['lbox'] = dict(x=x, y=y, w=bw, h=th)
    b['foot'] = union(b, b['lbox'])
    return b


def layout_lanes(S, F, top, bottom):
    """Swimlanes: one band per group (list order, ungrouped nodes in a last band) separated by
    hairlines, lane names in mono at the left; nodes placed by rank left to right inside their
    lane, each a ring with its text hanging right of it under the wire line."""
    rank = ranks(S)
    R = max(rank.values()) + 1
    lanes = [(g, [n['id'] for n in S.nodes if n.get('group') == g['id']]) for g in S.groups]
    rest = [n['id'] for n in S.nodes if not n.get('group')]
    if rest:
        lanes.append((None, rest))
    W, r = S.W, F['ring']
    hr = max(mark(F, n, 0, 0)['r'] for n in S.nodes)
    name_w = min(0.2 * W, max(120, max(text_w(g['label'], F['mono'], True) * 1.1 for g in S.groups) + 40))
    need = need_w(S, F)

    def text_col(x0):
        lw = (W - 24 - x0 + 24) / R - 2 * hr - LABEL_GAP - 24
        return min(240, lw)
    side = text_col(24 + name_w) >= need                 # lane names in a left column?
    x0 = 24 + (name_w if side else 8)
    lw = text_col(x0)
    if lw < need * 0.85:
        warn(f'lanes: {R} ranks leave a {lw:.0f} px text column (labels need ~{need:.0f}); widen --viewbox or shorten labels')
    labs = {n['id']: label_lines(n, F, max(lw, 60)) for n in S.nodes}
    block = 2 * hr + LABEL_GAP + max(block_w(v, F) for v in labs.values())
    pitch_x = (W - 24 - x0 - block) / (R - 1) if R > 1 else 0
    head = 0 if side else F['mono'] * 1.25 + 10
    sub_rows = [max(sum(1 for i in m if rank[i] == rr) for rr in range(R)) for _, m in lanes]
    row_h = max(2 * hr, hr + 8 + max(text_h(v, F) for v in labs.values())) + 8
    inner = bottom - top - head * len(lanes)
    pitch_y = inner / sum(sub_rows)
    tight = pitch_y < row_h                          # no room to hang the text under the wire line
    if tight:
        row_h = max(2 * hr, max(text_h(v, F) for v in labs.values())) + 8
    nodes, conts, y = {}, [], top
    order = [n['id'] for n in S.nodes]
    for li, ((g, members), rows) in enumerate(zip(lanes, sub_rows)):
        lh = head + rows * pitch_y
        conts.append(dict(key=g['id'] if g else 'c-lane', group=g, x=24, y=y, w=W - 48, h=lh,
                          label=g['label'] if g else '', style='lane', members=members, order=li,
                          side=side, name_w=name_w))
        for rr in range(R):
            col = sorted((i for i in members if rank[i] == rr), key=order.index)
            for k, i in enumerate(col):
                b = mark(F, S.node[i], x0 + hr + rr * pitch_x, 0)
                if tight:
                    b = mark(F, S.node[i], b['cx'], y + head + (k + 0.5) * pitch_y)
                    nodes[i] = put_label(b, labs[i], 'right', F)
                else:
                    b = mark(F, S.node[i], b['cx'], y + head + k * pitch_y + (pitch_y - (row_h - 8)) / 2 + hr)
                    nodes[i] = put_label_low(b, labs[i], F)
        y += lh
    ports = {}                                        # cross-lane wires share a side: spread them
    for e in S.edges:
        if e['from'] in lane_of(lanes, e['to']):
            continue
        a, b = nodes[e['from']], nodes[e['to']]
        down = b['cy'] > a['cy']
        ports.setdefault((e['from'], down), []).append((b['cx'], e['id'], 0))
        ports.setdefault((e['to'], not down), []).append((a['cx'], e['id'], 1))
    px = {}
    for (nid, _), lst in ports.items():
        lst.sort()
        w = nodes[nid]['r'] * (0.9 if nodes[nid]['shape'] != 'diamond' else 0)
        for k, (_, eid, end) in enumerate(lst):
            px[eid, end] = (k - (len(lst) - 1) / 2) * (w / max(1, len(lst) - 1)) if len(lst) > 1 else 0
    edges = {}
    for e in S.edges:
        a, b = nodes[e['from']], nodes[e['to']]
        same = e['from'] in lane_of(lanes, e['to'])
        (ax, ay), (bx, by) = (a['cx'], a['cy']), (b['cx'], b['cy'])
        if same and abs(ay - by) < 1 and abs(rank[e['to']] - rank[e['from']]) == 1 and tight:
            c = bottom_arc(a, b, 26)
        elif same and abs(ay - by) < 1 and abs(rank[e['to']] - rank[e['from']]) == 1:
            s = 1 if bx > ax else -1
            c = straight((ring_port(a, s, 0), ay), (ring_port(b, -s, 0), by))
        elif same and abs(ay - by) < 1:
            c = top_arc(a, b, 30 if rank[e['to']] > rank[e['from']] else 44)
        elif not same:                                # across lanes: leave by the top or bottom
            sy = 1 if by > ay else -1

            def yport(m, dx, s_):
                if m['shape'] == 'diamond':
                    return m['cy'] + s_ * (m['r'] + WIRE_GAP)
                return m['cy'] + s_ * (math.sqrt(max(0.0, m['r'] ** 2 - dx * dx)) + WIRE_GAP)
            p0 = (ax + px[e['id'], 0], yport(a, px[e['id'], 0], sy))
            p3 = (bx + px[e['id'], 1], yport(b, px[e['id'], 1], -sy))
            k = abs(p3[1] - p0[1]) / 2
            edges[e['id']] = cubic(p0, (p0[0], p0[1] + sy * k), (p3[0], p3[1] - sy * k), p3)
            continue
        else:
            c = ring_route(a, b)
        if f'{e["to"]}>{e["from"]}' in S.edge:          # a reverse pair: pull the two wires apart
            c = offset_curve(c, 9)
        edges[e['id']] = c
    return dict(nodes=nodes, edges=edges, containers=conts)


def lane_of(lanes, nid):
    return next(m for _, m in lanes if nid in m)


def offset_curve(c, d):
    """Shift a cubic sideways (to its right) by d."""
    dx, dy = c[3][0] - c[0][0], c[3][1] - c[0][1]
    ln = math.hypot(dx, dy) or 1
    ox, oy = -dy / ln * d, dx / ln * d
    return tuple((p[0] + ox, p[1] + oy) for p in c)


def layout_timeline(S, F, top, bottom):
    """One axis with dots; labels alternate above and below on thin leaders, the `at` label sits
    on the other side of the dot; groups (eras) are hairline brackets under everything."""
    n, W = len(S.nodes), S.W
    alt = n >= 4
    m = 120
    for _ in range(3):                         # the end labels stay inside the viewBox
        spacing = (W - 2 * m) / max(1, n - 1)
        lw = min(300, (2 * spacing if alt else spacing) - 40) if n > 1 else W - 96
        m = max(80, 24 + min(lw, max(need_w(S, F), 0) + 8) / 2 + 4)
    xs = [W / 2] if n == 1 else [m + i * (W - 2 * m) / (n - 1) for i in range(n)]
    labs = {nd['id']: label_lines(nd, F, lw) for nd in S.nodes}
    below = {nd['id']: alt and i % 2 == 1 for i, nd in enumerate(S.nodes)}
    dot, lead, at_gap = F['dot'], 40, 12
    th_up = max([text_h(labs[i], F) for i in labs if not below[i]] or [0])
    th_dn = max([text_h(labs[i], F) for i in labs if below[i]] or [0])
    at_h = dot + at_gap + F['mono']
    up = max(dot + lead + th_up if th_up else 0, at_h if any(below.values()) else 0)
    down = max(dot + lead + th_dn if th_dn else 0, at_h)
    # eras: bracket spans, stacked where they overlap
    half = min(40, (xs[1] - xs[0]) * 0.4) if n > 1 else 40
    spans, levels = [], []
    for g in S.groups:
        mx = [xs[k] for k, nd in enumerate(S.nodes) if nd.get('group') == g['id']]
        x0, x1 = min(mx) - half, max(mx) + half
        lv = 0
        while any(l == lv and a < x1 + 8 and x0 < b + 8 for a, b, l in levels):
            lv += 1
        levels.append((x0, x1, lv))
        spans.append((g, x0, x1, lv))
    lvh = F['sub'] * 1.25 + 22
    nlv = max([lv for *_, lv in spans] + [-1]) + 1
    extra = 24 + nlv * lvh if nlv else 0
    ay = top + max(0, (bottom - top - (up + down + extra)) / 2) + up
    nodes, back = {}, []
    for i, nd in enumerate(S.nodes):
        b = put_label(mark(F, nd, xs[i], ay, 'dot'), labs[nd['id']], 'below' if below[nd['id']] else 'above', F, lead)
        ya = ay - dot - at_gap - F['mono'] * 0.2 if below[nd['id']] else ay + dot + at_gap + F['mono'] * 0.8
        b['at'] = (xs[i], ya)
        b['atbox'] = dict(x=xs[i] - text_w(str(nd['at']), F['mono'], True) / 2, y=ya - F['mono'] * 0.8,
                          w=text_w(str(nd['at']), F['mono'], True), h=F['mono'])
        b['foot'] = union(b['foot'], b['atbox'])
        b['leader'] = (xs[i], ay + (dot + 4 if below[nd['id']] else -dot - 4),
                       b['lbox']['y'] - 6 if below[nd['id']] else b['lbox']['y'] + b['lbox']['h'] + 6)
        nodes[nd['id']] = b
    axis = f'M {f1(xs[0] - (24 if n > 1 else 60))},{f1(ay)} L {f1(xs[-1] + (24 if n > 1 else 60))},{f1(ay)}'
    back.append(f'<path class="{S.name}-axis" d="{axis}"/>')
    back.append(f'<path id="{S.name}-progress" class="{S.name}-prog" d="{axis}" pathLength="100"/>')
    yb = ay + down + 24
    brackets = [(g, x0, x1, yb + lv * lvh) for g, x0, x1, lv in spans]
    edges = {e['id']: ring_route(nodes[e['from']], nodes[e['to']]) for e in S.edges}
    return dict(nodes=nodes, edges=edges, back=back, brackets=brackets)


def layout_states(S, F, top, bottom):
    """Rings on an ellipse, each label outside it (radially), transitions as thin arcs that bow
    toward the centre so the outside stays free for the text."""
    n = len(S.nodes)
    lw = min(260, max(160, need_w(S, F) + 8))
    labs = {nd['id']: label_lines(nd, F, lw) for nd in S.nodes}
    cx0, cy0 = S.W / 2, (top + bottom) / 2
    ang = [math.pi + i * 2 * math.pi / n for i in range(n)]
    sides = []
    for a in ang:
        s, c = math.sin(a), math.cos(a)
        sides.append(('above' if s < 0 else 'below') if abs(s) >= 0.5 else ('left' if c < 0 else 'right'))
    rx, ry = (S.W - 48) / 2, (bottom - top) / 2
    for i, nd in enumerate(S.nodes):
        b = mark(F, nd, 0, 0)
        L = labs[nd['id']]
        bw, th = block_w(L, F), text_h(L, F)
        ex = b['r'] + LABEL_GAP + bw if sides[i] in ('left', 'right') else max(b['r'], bw / 2)
        ey = b['r'] + LABEL_GAP + th if sides[i] in ('above', 'below') else max(b['r'], th / 2)
        c, s = math.cos(ang[i]), math.sin(ang[i])
        if abs(c) > 1e-6:
            rx = min(rx, (S.W / 2 - 24 - ex) / abs(c))
        else:
            rx = min(rx, (S.W / 2 - 24 - ex) / 0.3)
        if abs(s) > 1e-6:
            ry = min(ry, ((bottom - top) / 2 - ey) / abs(s))
    rx, ry = max(rx, 60), max(ry, 40)
    rx = min(rx, max(ry * 2.6, (S.W - 48) * 0.3))
    nodes = {}
    for i, nd in enumerate(S.nodes):
        b = mark(F, nd, cx0 + rx * math.cos(ang[i]), cy0 + ry * math.sin(ang[i]))
        nodes[nd['id']] = put_label(b, labs[nd['id']], sides[i], F)
    edges, idx = {}, {nd['id']: i for i, nd in enumerate(S.nodes)}
    for e in S.edges:
        a, b = nodes[e['from']], nodes[e['to']]
        pa, pb = (a['cx'], a['cy']), (b['cx'], b['cy'])
        m = lerp(pa, pb, 0.5)
        dx, dy = m[0] - cx0, m[1] - cy0
        d = math.hypot(dx, dy) or 1
        chord = math.hypot(pb[0] - pa[0], pb[1] - pa[1]) or 1
        bulge = -(0.14 * chord + 12)                 # toward the centre
        if f'{e["to"]}>{e["from"]}' in S.edge and idx[e['from']] > idx[e['to']]:
            bulge = -bulge
        if d < 0.15 * chord:            # chord through the centre: bend sideways
            dx, dy, d = -(pb[1] - pa[1]), pb[0] - pa[0], chord
            bulge = abs(bulge)
        q = (m[0] + dx / d * bulge, m[1] + dy / d * bulge)
        edges[e['id']] = quad(edge_end(a, q), q, edge_end(b, q))
    return dict(nodes=nodes, edges=edges)


def edge_end(b, toward):
    """Point on a mark's outline (plus the wire gap) in the direction of `toward`."""
    dx, dy = toward[0] - b['cx'], toward[1] - b['cy']
    d = math.hypot(dx, dy) or 1
    rr = b['r'] if b['shape'] != 'diamond' else b['r'] / (abs(dx / d) + abs(dy / d))
    return (b['cx'] + dx / d * (rr + WIRE_GAP), b['cy'] + dy / d * (rr + WIRE_GAP))


def container_label(S, members):
    """A group whose members are exactly these nodes names the column / band."""
    for g in S.groups:
        gm = {n['id'] for n in S.nodes if n.get('group') == g['id']}
        if gm and gm <= set(members):
            return g
    return None


def compare_sides(S):
    """Column order: left before right; any other side values in order of first appearance."""
    seen = list(dict.fromkeys(n['side'] for n in S.nodes))
    if set(seen) <= {'left', 'right'}:
        return [x for x in ('left', 'right') if x in seen] or ['left']
    return seen


def row_text(n, F, w, stack=False):
    """Text of a compare row: None = label left and sub (mono) right on one line; otherwise a list
    of (text, role) lines, the label wrapped and the sub on its own line below. stack=True (some
    row of the slide needs two lines) stacks every row that has a sub, so the rows match."""
    one = text_w(n['label'], F['lbl']) + (text_w(n['sub'], F['sub'], True) + 32 if n['sub'] else 0) + 8 <= w
    if one and not (stack and n['sub']):
        return None
    out = [(t, 'lbl') for t in wrap(n['label'], F['lbl'], w - 8, 3)]
    if n['sub']:
        out += [(t, 'sub') for t in wrap(n['sub'], F['sub'], w - 8, 2, True)]
    return out


def text_h(lines, F):
    return sum(F[r] * 1.25 for _, r in lines) - F[lines[-1][1]] * 0.25 if lines else F['lbl']


def layout_compare(S, F, top, bottom):
    """Columns separated by space only: a header, then rows of text with hairline rules."""
    W, nodes, conts = S.W, {}, []
    sides = compare_sides(S)
    C, gap = len(sides), 80 if len(sides) == 2 else 56
    if C > 4:
        warn(f'compare: {C} columns (sides {", ".join(sides)}); more than 4 is hard to read')
    pw = (W - 48 - 2 * 16 - (C - 1) * gap) / C
    cols = {sd: [n['id'] for n in S.nodes if n['side'] == sd] for sd in sides}
    rows = max(len(m) for m in cols.values())
    for sd, m in cols.items():
        if len(m) > 5:
            warn(f'compare: side {sd} has {len(m)} rows (archetypes.md: up to 5 per side); split or merge rows')
    hy = top + F['head'] * 1.25 + 22
    pitch = (bottom - hy) / max(1, rows)
    stack = any(row_text(n, F, pw - 16) for n in S.nodes)
    need = max(text_h(row_text(n, F, pw - 16, stack) or [('x', 'lbl')], F) + 24 for n in S.nodes)
    h = min(pitch, max(56, need))
    if need > pitch:
        warn(f'compare: rows need {need:.0f} px but only {pitch:.0f} fit; shorten text or raise size H')
    lr = C == 2 and sides == ['left', 'right']
    for k, sd in enumerate(sides):
        px = 24 + 16 + k * (pw + gap)
        members = cols[sd]
        g = container_label(S, members)
        label = g['label'] if g else (('Before', 'After')[k] if lr else sd.replace('-', ' ').capitalize())
        conts.append(dict(key=g['id'] if g else f'c-{sd}', group=g, x=px, y=top, w=pw, h=bottom - top,
                          label=label, style='panel', members=members))
        for r, i in enumerate(members):
            y = hy + r * pitch + (pitch - h) / 2
            nodes[i] = dict(x=px, y=y, w=pw, h=h, cx=px + pw / 2, cy=y + h / 2, r=0, shape='row',
                            row=True, stack=stack, last=r == len(members) - 1)
    edges = {e['id']: ring_route(nodes[e['from']], nodes[e['to']]) for e in S.edges}
    return dict(nodes=nodes, edges=edges, containers=conts)


def layout_layers(S, F, top, bottom):
    """Bands separated by hairlines, layer names in mono caps at the left; nodes are rings with
    their text hanging right of them, wires run vertically between bands."""
    levels = sorted({n['layer'] for n in S.nodes})
    L = len(levels)
    bh = (bottom - top) / L
    nodes, conts = {}, []
    names = []
    for lv in levels:
        members = [n['id'] for n in S.nodes if n['layer'] == lv]
        g = container_label(S, members)
        names.append((members, g, g['label'] if g else f'Layer {lv}'))
    name_w = 24 + max(176, max(text_w(t, F['mono'], True) * 1.12 for *_, t in names) + 40)
    hr = max(mark(F, n, 0, 0)['r'] for n in S.nodes)
    for li, lv in enumerate(levels):
        y = bottom - (li + 1) * bh
        members, g, label = names[li]
        conts.append(dict(key=g['id'] if g else f'c-l{lv}', group=g, x=24, y=y, w=S.W - 48, h=bh,
                          label=label, style='band', members=members, order=li))
        slot = (S.W - 24 - name_w) / len(members)
        lw = min(280, slot - 2 * hr - LABEL_GAP - 32)
        for k, i in enumerate(members):
            lines = label_lines(S.node[i], F, max(lw, 60))
            blk = 2 * hr + LABEL_GAP + block_w(lines, F)
            th = text_h(lines, F)
            cy = y + bh / 2 - max(0, (8 + th) - hr) / 2
            b = mark(F, S.node[i], name_w + k * slot + max(0, (slot - blk) / 2) + hr, cy)
            nodes[i] = put_label_low(b, lines, F)
    edges = {}
    for e in S.edges:
        a, b = nodes[e['from']], nodes[e['to']]
        if abs(a['cy'] - b['cy']) < 1:
            s = 1 if b['cx'] > a['cx'] else -1
            rev = f'{e["to"]}>{e["from"]}' in S.edge
            if rev and s < 0:
                edges[e['id']] = top_arc(a, b, 28)
            else:
                edges[e['id']] = straight((ring_port(a, s, 0), a['cy']), (ring_port(b, -s, 0), b['cy']))
            continue
        down = b['cy'] > a['cy']
        off = -12 if down else 12
        ya = math.sqrt(max(0.0, a['r'] ** 2 - off * off)) + WIRE_GAP
        yb = math.sqrt(max(0.0, b['r'] ** 2 - off * off)) + WIRE_GAP
        p0 = (a['cx'] + off, a['cy'] + (ya if down else -ya))
        p3 = (b['cx'] + off, b['cy'] - (yb if down else -yb))
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
    """Phase times in seconds from the spec, for every control (step uses the once pass). once and
    step end on the final state (no reset); loop fades back to empty in the last RESET s."""

    def __init__(self, S):
        self.once = S.mode == 'once'
        n = len(S.phases)
        self.t = [float(p['t']) for p in S.phases]
        self.end = float(S.cycle)
        self.rst = self.end if self.once else S.cycle - RESET
        self.act = list(self.t)
        self.win = [(self.t[i + 1] if i + 1 < n else self.rst) - self.t[i] for i in range(n)]
        self.draw_end = self.t[-1] if n > 1 else self.rst
        self.n = n

    def marks(self, S):
        """data-anim-phases: the start of every phase after the first, so the hold's start is the last
        mark; without a hold phase (or with a single phase) the end of the motion closes the list.
        One decimal, strictly ascending, each > 0 and <= the pass."""
        ms = [round(t, 1) for t in self.t[1:]]
        if not ms or S.phases[-1]['label'] != 'hold':
            ms.append(round(self.rst, 1))
        out = []
        for m in ms:
            if 0 < m <= self.end and (not out or m > out[-1]):
                out.append(m)
        return ','.join(f1(m) for m in out) or f1(self.end)

    def xtime(self, frac):
        return frac * self.draw_end

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
        return 0 if m < 2 else k * min(0.08, 0.45 / (m - 1))

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
            entry[e['id']] = (a + 0.3, b)
    ch = scene.get('chart')
    if ch:
        for s in ch['series']:
            s['drawn'] = s['s']['id'] not in entry
            entry.setdefault(s['s']['id'], (0, 0))
        for ev in ch['events']:
            if ev['e']['id'] not in entry:
                t = T.xtime(ev['frac'])
                entry[ev['e']['id']] = (t, T.phase_at(t))

    named = {x for p in S.phases for x in p['show']}
    for key, (t, i) in entry.items():
        if key not in rid:
            continue
        if T.once and i == 0 and key not in named and t < 0.8:
            continue    # once: the static frame is simply there; only the story enters (concurrency)
        anim.add(rid[key], 'opacity', t, 0.4, 0, 1)
        if key in S.edge and S.edge[key]['kind'] in ('flow', 'data'):
            # dash 100 + gap 120 at offset 101: no zero-length dash, so round caps paint no dot
            anim.add(rid[key] + '-w', 'stroke-dashoffset', t, 0.6, 101, 0, 'move')

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
            anim.add(el, 'opacity', T.act[i], 0.25, 0, 1)
            if j + 1 < T.n:
                anim.add(el, 'opacity', T.act[j + 1], 0.2, 1, 0, 'exit')
            i = j + 1
        anim.rest_over[el] = {'opacity': 1 if on[-1] else 0}
    for key in sorted({x for p in S.phases for x in p['active']}):
        if key in rid and key not in {s['id'] for s in S.series + S.events}:
            runs([key in p['active'] for p in S.phases], rid[key] + '-hl')
    if S.arch in ('pipeline', 'timeline'):        # a step that was lit and moved on settles in --anim-ok
        scene['ok'] = set()
        for n in S.nodes:
            on = [n['id'] in p['active'] for p in S.phases]
            if True not in on:
                continue
            j = on.index(True)
            while j + 1 < T.n and on[j + 1]:
                j += 1
            if j + 1 < T.n:
                anim.add(rid[n['id']] + '-ok', 'opacity', T.act[j + 1], 0.3, 0, 1)
                scene['ok'].add(n['id'])
    notes = [i for i, p in enumerate(S.phases) if p['note']]
    if notes and not S.phases[-1]['note']:
        warn(f'the last phase ({S.phases[-1]["label"]}) has no note, so the resting frame (PDF export) '
             f'keeps {S.phases[notes[-1]]["note"][:40]!r}; give it a note that summarises the story')
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
        lo, hi = 0.6, 1.0
        if T.once:
            lo = min(lo, max(0.3, T.win[i] / depth - 0.15))   # short once phases: the hop fits its phase
        hop = max(lo, min(hi, T.win[i] / depth - 0.3))
        for eid in p['flow']:
            el, t0 = f'{N}-p{pk}', T.act[i] + 0.05 + pos[eid] * (hop + 0.3)
            anim.add(el, 'opacity', t0, 0.1, 0, 1, 'linear')
            anim.add(el, 'offset-distance', t0 + 0.1, hop, '0%', '100%', 'move')
            anim.add(el, 'opacity', t0 + 0.1 + hop, 0.15, 1, 0, 'exit')
            scene.setdefault('packets', []).append((el, eid))
            pk += 1

    if S.arch == 'timeline':                      # progress line reaches each milestone as it enters
        n, cur, last = len(S.nodes), 101.0, 0.0     # 101: fully hidden, no round-cap dot
        for i, nd in sorted(enumerate(S.nodes), key=lambda x: entry[x[1]['id']][0]):
            v = 100 - 100 * i / max(1, n - 1)
            t = entry[nd['id']][0]
            if v < cur:
                t0 = max(last, t - 0.6)
                anim.add(f'{N}-progress', 'stroke-dashoffset', t0, max(0.2, t - t0), cur, v, 'move')
                last = t
            if v < cur:
                cur = v
        anim.rest_over[f'{N}-progress'] = {'stroke-dashoffset': 0}
    if ch:
        pw = ch['R'] - ch['L']
        anim.add(f'{N}-clip-r', 'width', 0, T.draw_end, '0px', f'{f1(pw)}px', 'linear')
        for s in ch['series']:
            sid = rid[s['s']['id']]
            if not s['drawn']:
                continue
            anim.add(sid + '-end', 'opacity', T.xtime(1) - 0.3, 0.3, 0, 1)
            if T.once:     # once: the head dot appears at the end instead of riding
                anim.add(sid + '-dot', 'opacity', T.xtime(1) - 0.3, 0.2, 0, 1)
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
def css_keyframes(el, segs, T, marks, final=None):
    """loop: back to the initial value at 100 % (reset); once: the 100 % stop is the resting
    frame (final), so the pass ends exactly on the ungated still and fill-mode holds it."""
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
        if T.once:
            put(T.end, prop, (final or {}).get(prop, cur))
        else:
            put(T.rst, prop, cur, 'exit')
            put(T.end, prop, init)
    out = [f'@keyframes {el} {{']
    for t in sorted(stops):
        props, ease = stops[t]
        body = ' '.join(f'{k}: {v};' for k, v in props.items())
        if ease:
            body += f' animation-timing-function: {EASE[ease]};'
        pct = f'{t / T.end * 100:.2f}'.rstrip('0').rstrip('.')
        out.append(f'  {pct}% {{ {body} }}  /* {f1(t)}s{" " + marks[t] if t in marks else ""} */')
    return '\n'.join(out + ['}'])


def text_lines(x, y, h, lines, anchor='middle'):
    """Stacked <text> lines (text, class, size) centred vertically in y .. y + h."""
    total = sum(fs * 1.25 for _, _, fs in lines) - lines[-1][2] * 0.25
    yt, out = y + (h - total) / 2, []
    for txt, cls, fs in lines:
        out.append(f'<text class="{cls}" x="{f1(x)}" y="{f1(yt + fs * 0.8)}" '
                   f'text-anchor="{anchor}">{escape(txt)}</text>')
        yt += fs * 1.25
    return ''.join(out), total


def text_block(N, lab, F, only=None, extra=''):
    """A node's text lines at the place put_label chose: label in --anim-font, sub in mono muted."""
    out, yt = [], lab['y']
    for t, r in lab['lines']:
        if only is None or r == only:
            cls = f'{N}-t {N}-lbl' if r == 'lbl' else f'{N}-t {N}-sub'
            out.append(f'<text class="{cls}{extra}" x="{f1(lab["x"])}" y="{f1(yt + F[r] * 0.8)}" '
                       f'text-anchor="{lab["anchor"]}">{escape(t)}</text>')
        yt += F[r] * 1.25
    return ''.join(out)


def mark_svg(b, cls, el_id=''):
    a = f' class="{cls}"' + (f' id="{el_id}"' if el_id else '')
    if b['shape'] == 'diamond':
        x, y, r = b['cx'], b['cy'], b['r']
        return f'<path{a} d="M {pt((x - r, y))} L {pt((x, y - r))} L {pt((x + r, y))} L {pt((x, y + r))} Z"/>'
    return f'<circle{a} cx="{f1(b["cx"])}" cy="{f1(b["cy"])}" r="{f1(b["r"])}"/>'


GLYPHS = {   # line glyphs inside a ring, drawn round (0, 0) for r 34
    'actor': 'M -5,-7 a 5,5 0 1 0 10,0 a 5,5 0 1 0 -10,0 M -11,12 Q 0,-2 11,12',
    'store': 'M -11,-8 A 11,4 0 0 0 11,-8 A 11,4 0 0 0 -11,-8 V 8 A 11,4 0 0 0 11,8 V -8 M -11,0 A 11,4 0 0 0 11,0',
    'data': 'M -9,-12 H 4 L 10,-6 V 12 H -9 Z M 4,-12 V -6 H 10',
    'external': 'M -12,0 a 12,12 0 1 0 24,0 a 12,12 0 1 0 -24,0 M -12,0 H 12 M 0,-12 a 5,12 0 0 0 0,24 a 5,12 0 0 0 0,-24',
    'milestone': 'M -7,12 V -12 L 9,-6 L -7,0',
}


def inner(S, F, n, b, k, variant=''):
    """What sits inside a ring: the step number (pipeline) or a line glyph per kind."""
    N = S.name
    v = f' {N}-in-{variant}' if variant else ''
    if b['shape'] != 'ring':
        return ''
    if S.arch == 'pipeline':
        return (f'<text class="{N}-t {N}-num{v}" x="{f1(b["cx"])}" y="{f1(b["cy"] + F["num"] * 0.36)}" '
                f'text-anchor="middle">{k + 1}</text>')
    d = GLYPHS.get(n['kind'])
    if not d:
        return ''
    sc = b['r'] / 34
    tr = f'translate({f1(b["cx"])} {f1(b["cy"])})' + (f' scale({sc:.3g})' if abs(sc - 1) > 0.01 else '')
    return f'<path class="{N}-glyph{v}" transform="{tr}" d="{d}"/>'


def label_box(S, F, scene, e):
    """Box of an edge label: centred where the layout put it, else on the wire's middle (lifted
    above a straight horizontal wire)."""
    if e['id'] in scene.get('labels', {}):
        return edge_label_box(S, F, e, scene['labels'][e['id']])
    c = scene['edges'][e['id']]
    m, c0 = bez_mid(c), segs(c)[0]
    ly = m[1] - 12 if abs(c0[3][1] - c0[0][1]) < 4 and abs(c0[1][1] - c0[0][1]) < 4 else m[1] + F['edge'] * 0.35
    tw = text_w(e['label'], F['edge'], True) + 12
    return dict(x=m[0] - tw / 2, y=ly - F['edge'] * 0.9, w=tw, h=F['edge'] * 1.25)


def scene_group_box(S, F, scene, gid):
    return dict(scene['gboxes'][gid]) if gid in scene.get('gboxes', {}) else group_box(S, scene['nodes'], gid, F)


def drawn_groups(S, scene):
    used = {c['group']['id'] for c in scene.get('containers', []) if c['group']}
    if S.arch == 'timeline':
        used |= set(S.group)
    return [g for g in S.groups if g['id'] not in used]


def illus_box(S, F, top):
    tw = text_w('illustrative', F['mono'], True) + 24
    h = F['mono'] + 14
    y = (top - 22 - F['mono'] - 4) if S.title else 24
    return dict(x=S.W - 24 - tw, y=y, w=tw, h=h)


def outside(S, F, scene, frame_info):
    """Everything drawn that leaves the viewBox (or runs into the caption row): [(what, x0, y0, x1, y1)]."""
    top, bottom, strip, has_note = frame_info
    ylim = S.H - strip - 8 if has_note else S.H
    items = [(f'node {i}', foot(b)) for i, b in scene['nodes'].items()]
    items += [(f'{c["style"]} {c["key"]}', c) for c in scene.get('containers', [])]
    items += [(f'group {g["id"]}', scene_group_box(S, F, scene, g['id'])) for g in drawn_groups(S, scene)
              if any(n.get('group') == g['id'] for n in S.nodes)]
    for g, x0, x1, y in scene.get('brackets', []):
        items.append((f'era {g["id"]}', dict(x=x0, y=y - 14, w=x1 - x0, h=14 + F['sub'] * 1.25 + 6)))
    items += [(f'label of {e["id"]}', label_box(S, F, scene, e)) for e in S.edges if e['label']]
    for e in S.edges:
        pts = sample(scene['edges'][e['id']], 12)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        items.append((f'edge {e["id"]}', dict(x=min(xs) - 2, y=min(ys) - 2, w=max(xs) - min(xs) + 4, h=max(ys) - min(ys) + 4)))
    out = [(f'{c} overlap (no room between rows)', 0, 0, 0, S.H * 2) for c in scene.get('conflicts', [])]
    for what, b in items:
        x0, y0, x1, y1 = b['x'], b['y'], b['x'] + b['w'], b['y'] + b['h']
        if x0 < -0.5 or y0 < -0.5 or x1 > S.W + 0.5 or y1 > ylim + 0.5:
            out.append((what, x0, y0, x1, y1))
    return out


def bracket_d(x0, x1, y, gap0, gap1, tick):
    """Hairline bracket from x0 to x1 at y with ticks of length `tick` (negative: up), open
    between gap0 and gap1 where its label sits."""
    if gap1 <= gap0:
        return f'M {f1(x0)},{f1(y + tick)} V {f1(y)} H {f1(x1)} V {f1(y + tick)}'
    return (f'M {f1(x0)},{f1(y + tick)} V {f1(y)} H {f1(gap0)} '
            f'M {f1(gap1)},{f1(y)} H {f1(x1)} V {f1(y + tick)}')


def emit(S, args, F, scene, T, anim, rid, frame_info):
    N = S.name
    top, bottom, strip, has_note = frame_info
    active_ids = {x for p in S.phases for x in p['active']}
    over = []                                       # overflow warnings
    svg = []
    if S.title:
        svg.append(f'<text class="{N}-t {N}-title" x="24" y="{f1(top - 22)}">{escape(S.title)}</text>')
    if S.illustrative:
        b = illus_box(S, F, top)
        svg.append(f'<g class="{N}-illus"><rect class="{N}-tag" x="{f1(b["x"])}" y="{f1(b["y"])}" '
                   f'width="{f1(b["w"])}" height="{f1(b["h"])}" rx="4"/><text class="{N}-t {N}-mono" '
                   f'x="{f1(b["x"] + b["w"] / 2)}" y="{f1(b["y"] + b["h"] / 2 + F["mono"] * 0.35)}" '
                   f'text-anchor="middle">illustrative</text></g>')
    svg += scene.get('back', [])

    # State layer: every highlight copy, every settled (ok) copy and the captions live in ONE <g>
    # drawn after the figure, so a phase change (old highlight out, new in, status settles,
    # caption swaps) is one opacity swap in one group, not five separate moves (concurrency).
    state = []

    def hl_group(el, body):
        state.append(f'<g id="{el}-hl" class="{N}-hlg"{anim.style(el + "-hl")}>{body}</g>')
        return ''

    # ---- containers: compare columns, layer bands, lanes (no panels: hairlines and names)
    for c in scene.get('containers', []):
        el = rid[c['key']]
        on = c['key'] in active_ids
        if c['style'] == 'lane':
            rule = (f'<path class="{N}-rule" d="M {f1(c["x"])},{f1(c["y"])} H {f1(c["x"] + c["w"])}"/>'
                    if c['order'] else '')
            if c['side']:
                lines = wrap(c['label'], F['mono'], c['name_w'] - 32, 3, True)
                mk = lambda extra: text_lines(c['x'], c['y'], c['h'],    # noqa: E731
                                              [(t, f'{N}-t {N}-lane{extra}', F['mono']) for t in lines], 'start')[0]
            else:
                lines = wrap(c['label'], F['mono'], c['w'] - 32, 1, True)
                mk = lambda extra: (f'<text class="{N}-t {N}-lane{extra}" x="{f1(c["x"] + 8)}" '   # noqa: E731
                                    f'y="{f1(c["y"] + 8 + F["mono"])}">{escape(lines[0])}</text>')
            if any(text_w(t, F['mono'], True) > (c['name_w'] - 24 if c['side'] else c['w'] - 32) for t in lines):
                warn(f'lane label {c["label"][:30]!r} is wider than its lane header; shorten it')
            body = rule + (mk('') if c['label'] else '')
            hl = hl_group(el, mk(f' {N}-acc')) if on and c['label'] else ''
        elif c['style'] == 'panel':
            hy = c['y'] + F['head'] * 0.85
            ry = c['y'] + F['head'] * 1.25 + 6
            head = (f'<text class="{N}-t {N}-head" x="{f1(c["x"])}" y="{f1(hy)}">{escape(c["label"])}</text>')
            rule = f'M {f1(c["x"])},{f1(ry)} H {f1(c["x"] + c["w"])}'
            if text_w(c['label'], F['head']) > c['w']:
                warn(f'column header {c["label"][:30]!r} is wider than its column; shorten it')
            body = head + f'<path class="{N}-rule {N}-rule-head" d="{rule}"/>'
            hl = hl_group(el, f'<path class="{N}-wire-hl" d="{rule}"/>'
                          + head.replace(f'{N}-head"', f'{N}-head {N}-acc"')) if on else ''
        else:
            ty = c['y'] + c['h'] / 2 + F['mono'] * 0.35
            name = (f'<text class="{N}-t {N}-band" x="48" y="{f1(ty)}">{escape(c["label"])}</text>')
            rule = (f'<path class="{N}-rule" d="M {f1(c["x"])},{f1(c["y"] + c["h"])} H {f1(c["x"] + c["w"])}"/>'
                    if c['order'] else '')
            body = rule + name
            hl = hl_group(el, name.replace(f'{N}-band"', f'{N}-band {N}-acc"')) if on else ''
        svg.append(f'<g id="{el}" class="{N}-cont"{anim.style(el)}>{body}{hl}</g>')

    # ---- groups: hairline brackets with a small mono label in the gap
    if S.arch == 'timeline':
        for g, x0, x1, y in scene.get('brackets', []):
            el, mid = rid[g['id']], (x0 + x1) / 2
            tw = text_w(g['label'], F['sub'], True)
            inline = tw + 40 <= x1 - x0
            d = bracket_d(x0, x1, y, mid - tw / 2 - 12, mid + tw / 2 + 12, -12) if inline else bracket_d(x0, x1, y, 0, 0, -12)
            ty = y + F['sub'] * 0.35 if inline else y + F['sub'] + 8
            if not inline and tw > x1 - x0 + 40:
                warn(f'era {g["id"]}: bracket label is wider than its span; shorten it')
            hl = hl_group(el, f'<path class="{N}-wire-hl" d="{d}"/>') \
                if g['id'] in active_ids else ''
            svg.append(f'<g id="{el}" class="{N}-group"{anim.style(el)}><path class="{N}-bracket" d="{d}"/>{hl}'
                       f'<text class="{N}-t {N}-glbl" x="{f1(mid)}" y="{f1(ty)}" text-anchor="middle">'
                       f'{escape(g["label"])}</text></g>')
    for g in drawn_groups(S, scene):
        box = scene_group_box(S, F, scene, g['id'])
        x0, x1, y = box['x'], box['x'] + box['w'], box['y'] + F['sub'] * 0.5
        glines = group_label_lines(g, F, box['w'])
        tw = max(text_w(t, F['sub'], True) for t in glines)
        if tw > box['w'] - 40:
            warn(f'group {g["id"]}: label is wider than its bracket; shorten the label')
        for n in S.nodes:
            if n.get('group') != g['id'] and overlaps(foot(scene['nodes'][n['id']]), box):
                warn(f'group {g["id"]} bracket overlaps node {n["id"]}; move it by hand')
        el = rid[g['id']]
        d = bracket_d(x0, x1, y, x0 + 8, x0 + 20 + tw + 10, 16)
        hl = hl_group(el, f'<path class="{N}-wire-hl" d="{d}"/>') \
            if g['id'] in active_ids else ''
        svg.append(f'<g id="{el}" class="{N}-group"{anim.style(el)}><path class="{N}-bracket" d="{d}"/>{hl}'
                   + ''.join(f'<text class="{N}-t {N}-glbl" x="{f1(x0 + 20)}" y="{f1(y + F["sub"] * (0.35 + 1.25 * k))}">'
                             f'{escape(t)}</text>' for k, t in enumerate(glines)) + '</g>')

    # ---- wires
    plain = S.arch == 'pipeline'                    # a chain needs no arrowheads between neighbours
    for e in S.edges:
        c, el = scene['edges'][e['id']], rid[e['id']]
        draw = e['kind'] in ('flow', 'data')
        wire = (f'<path id="{el}-w" class="{N}-wire{" " + N + "-draw" if draw else ""}" d="{path_d(c)}"'
                f'{" pathLength=" + chr(34) + "100" + chr(34) if draw else ""}{anim.style(el + "-w")}/>')
        hl = hl_group(el, f'<path class="{N}-wire-hl" d="{path_d(c)}"/>') \
            if e['id'] in active_ids else ''
        chain = plain and len(segs(c)) == 1 and abs(c[0][1] - c[3][1]) < 1 and abs(c[1][1] - c[0][1]) < 1
        arrow = '' if chain else f'<path class="{N}-arrow" d="{arrow_d(c)}"/>'
        lab = ''
        if e['label']:
            lb = label_box(S, F, scene, e)
            lab = (f'<text class="{N}-t {N}-mono {N}-elbl" x="{f1(lb["x"] + lb["w"] / 2)}" '
                   f'y="{f1(lb["y"] + F["edge"] * 0.9)}" text-anchor="middle">{escape(e["label"])}</text>')
        svg.append(f'<g id="{el}" class="{N}-edge {N}-ek-{e["kind"]}"{anim.style(el)}>{wire}{hl}{arrow}{lab}</g>')

    # ---- nodes
    # glow budget: only one ring glows, the story's outcome (first node active in the last phase,
    # else the last node highlighted at all); every other highlight is a plain accent copy
    lit = [x for p in S.phases for x in p['active'] if x in S.node]
    glow_id = next((x for x in S.phases[-1]['active'] if x in S.node), lit[-1] if lit else None)
    for k, n in enumerate(S.nodes):
        b, el, kind = scene['nodes'][n['id']], rid[n['id']], n['kind']
        on = n['id'] in active_ids
        parts = []
        if b['shape'] == 'row':
            x = b['x'] + 16
            rt = row_text(n, F, b['w'] - 16, b.get('stack'))
            if rt:
                cls = {'lbl': f'{N}-t {N}-lbl', 'sub': f'{N}-t {N}-sub'}
                txt, total = text_lines(x, b['y'], b['h'], [(t, cls[r], F[r]) for t, r in rt], 'start')
                acc = text_lines(x, b['y'], b['h'], [(t, cls[r] + (f' {N}-acc' if r == 'lbl' else ' ' + N + '-ghost'), F[r])
                                                     for t, r in rt], 'start')[0]
                if total > b['h'] - 6 or any(line_w(t, r, F) > b['w'] - 24 for t, r in rt):
                    over.append(n['id'])
            else:
                ty = b['y'] + b['h'] / 2 + F['lbl'] * 0.35
                txt = f'<text class="{N}-t {N}-lbl" x="{f1(x)}" y="{f1(ty)}">{escape(n["label"])}</text>'
                acc = txt.replace(f'{N}-lbl"', f'{N}-lbl {N}-acc"')
                if n['sub']:
                    txt += (f'<text class="{N}-t {N}-sub" x="{f1(b["x"] + b["w"])}" y="{f1(ty)}" '
                            f'text-anchor="end">{escape(n["sub"])}</text>')
            parts.append(txt)
            if not b.get('last'):
                parts.append(f'<path class="{N}-rule" d="M {f1(b["x"])},{f1(b["y"] + b["h"])} H {f1(b["x"] + b["w"])}"/>')
            if on:
                tick = f'M {f1(b["x"] + 2)},{f1(b["y"] + 12)} V {f1(b["y"] + b["h"] - 12)}'
                parts.append(hl_group(el, f'<path class="{N}-wire-hl" d="{tick}"/>{acc}'))
            svg.append(f'<g id="{el}" class="{N}-node {N}-k-{kind}"{anim.style(el)}>{"".join(parts)}</g>')
            continue
        dot = b['shape'] == 'dot'
        if 'leader' in b:
            lx, l0, l1 = b['leader']
            parts.append(f'<path class="{N}-leader" d="M {f1(lx)},{f1(l0)} V {f1(l1)}"/>')
            parts.append(f'<text class="{N}-t {N}-at" x="{f1(b["at"][0])}" y="{f1(b["at"][1])}" '
                         f'text-anchor="middle">{escape(str(n["at"]))}</text>')
        base = f'{N}-dot' if dot else f'{N}-ring' + (f' {N}-ext' if kind == 'external' else '')
        parts.append(mark_svg(b, base))
        parts.append(inner(S, F, n, b, k))
        if n['id'] in scene.get('ok', ()):
            state.append(f'<g id="{el}-ok" class="{N}-okg"{anim.style(el + "-ok")}>'
                         + mark_svg(b, f'{base} {N}-is-ok') + inner(S, F, n, b, k, 'ok') + '</g>')
        if on:
            parts.append(hl_group(el, (mark_svg(b, f'{N}-glow') if n['id'] == glow_id else '')
                                  + mark_svg(b, f'{base} {N}-is-hl')
                                  + inner(S, F, n, b, k, 'hl')))
        parts.append(text_block(N, b['lab'], F))
        svg.append(f'<g id="{el}" class="{N}-node {N}-k-{kind}"{anim.style(el)}>{"".join(parts)}</g>')
    if over:
        warn(f'text may overflow its row in node(s) {", ".join(over)}: shorten the label, '
             'use sub, or pick a larger --viewbox / --rendered-width')

    # ---- chart
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
                       f'd="M {f1(x)},{f1(Tp)} V {f1(B)}"/><rect class="{N}-tag" x="{f1(tx - tw / 2)}" '
                       f'y="{f1(Tp - F["mono"] - 26)}" width="{f1(tw)}" height="{f1(F["mono"] + 16)}" rx="4"/>'
                       f'<text class="{N}-t {N}-mono" x="{f1(tx)}" y="{f1(Tp - 18 - F["mono"] * 0.15)}" '
                       f'text-anchor="middle">{escape(ev["e"]["label"])}</text></g>')
        for s in ch['series']:
            el, k = rid[s['s']['id']], s['k']
            clip = f' clip-path="url(#{N}-clip)"' if s['drawn'] else ''
            ex, ey = s['pts'][-1]
            dot = (f'<circle id="{el}-dot" class="{N}-tip {N}-f{k}" cx="0" cy="0" r="7"'
                   f'{anim.style(el + "-dot") or " style=" + chr(34) + f"transform:translate({f1(ex)}px,{f1(ey)}px)" + chr(34)}/>'
                   if s['drawn'] else '')
            if dot and 'transform' not in anim.rest(el + '-dot'):
                dot = dot.replace('cx="0" cy="0"', f'cx="{f1(ex)}" cy="{f1(ey)}"')
            glow = ''    # lines never glow (glow budget: one glowing element, a node ring)
            svg.append(f'<g id="{el}" class="{N}-series"{anim.style(el)}>{glow}<path class="{N}-ser {N}-c{k}" '
                       f'd="{s["d"]}"{clip}/>{dot}<text id="{el}-end" class="{N}-t {N}-lbl {N}-f{k}" '
                       f'x="{f1(ex + 14)}" y="{f1(s["ly"])}"{anim.style(el + "-end")}>{escape(s["s"]["label"])}</text></g>')

    # ---- caption: plain centred text, cross-faded per phase (inside the state layer)
    if has_note:
        notes = [p['note'] for p in S.phases if p['note']]
        for k, t in enumerate(notes):
            if text_w(t, F['note']) > S.W - 80:
                warn(f'note {t[:30]!r}... is wider than the caption row')
            state.append(f'<text id="{N}-note{k}" class="{N}-t {N}-note" x="{f1(S.W / 2)}" '
                         f'y="{f1(S.H - 8 - strip / 2 + F["note"] * 0.35)}" text-anchor="middle"'
                         f'{anim.style(f"{N}-note{k}")}>{escape(t)}</text>')
    if state:
        svg.append(f'<g id="{N}-state" class="{N}-state">')
        svg += ['  ' + x for x in state]
        svg.append('</g>')

    # ---- packets: accent dots riding the wires
    for el, eid in scene.get('packets', []):
        e = S.edge[eid]
        r = 10 if S.arch == 'states' else 8
        svg.append(f'<circle id="{el}" class="{N}-pkt{" " + N + "-pkt-event" if e["kind"] == "event" else ""}" '
                   f'r="{r}"{anim.style(el, f"offset-path:var(--{rid[eid]})")}/>')
    return svg


def css(S, F, T, anim, scene, rid):
    N, A = S.name, f'.anim-{S.name}'
    ink = 'color-mix(in srgb, var(--anim-muted) 55%, var(--anim-bg))'      # rings and wires at rest
    rules = f"""{A} {{
  --anim-bg:       var(--anim-theme-bg,       #0F1E27);
  --anim-panel:    var(--anim-theme-panel,    #0D1820);
  --anim-line:     var(--anim-theme-line,     #2A3D49);
  --anim-fg:       var(--anim-theme-fg,       #E6EDF0);
  --anim-muted:    var(--anim-theme-muted,    #93A7B2);
  --anim-accent:   var(--anim-theme-accent,   #34D1BF);
  --anim-accent-2: var(--anim-theme-accent-2, #FF8A3D);
  --anim-ok:       var(--anim-theme-ok,       #8ED7AD);
  --anim-warn:     var(--anim-theme-warn,     #FFD15C);
  --anim-danger:   var(--anim-theme-danger,   #FF6B6B);
  --anim-font:     var(--anim-theme-font,     system-ui, sans-serif);
  --anim-mono:     var(--anim-theme-mono,     ui-monospace, monospace);
  display: block; width: 100%; height: 100%;
}}
{A} svg {{ display: block; width: 100%; height: 100%; max-width: none; overflow: visible; }}
/* type: labels in --anim-font 600, everything secondary in mono muted */
{A} .{N}-t {{ font-family: var(--anim-font); fill: var(--anim-fg); }}
{A} .{N}-title {{ font-size: {F['title']}px; font-weight: 700; }}
{A} .{N}-head {{ font-size: {F['head']}px; font-weight: 600; }}
{A} .{N}-lbl {{ font-size: {F['lbl']}px; font-weight: 600; }}
{A} .{N}-sub, {A} .{N}-mono, {A} .{N}-at, {A} .{N}-glbl, {A} .{N}-lane, {A} .{N}-band {{ font-family: var(--anim-mono); font-weight: 400; fill: var(--anim-muted); }}
{A} .{N}-sub {{ font-size: {F['sub']}px; }}
{A} .{N}-mono, {A} .{N}-at, {A} .{N}-lane {{ font-size: {F['mono']}px; }}
{A} .{N}-glbl {{ font-size: {F['sub']}px; letter-spacing: .04em; }}
{A} .{N}-band {{ font-size: {F['mono']}px; letter-spacing: .1em; text-transform: uppercase; }}
{A} .{N}-num {{ font-family: var(--anim-mono); font-size: {F['num']}px; fill: var(--anim-muted); }}
{A} .{N}-elbl {{ paint-order: stroke; stroke: var(--anim-bg); stroke-width: 6px; stroke-linejoin: round; }}
{A} .{N}-note {{ font-size: {F['note']}px; font-weight: 400; }}
{A} .{N}-acc {{ fill: var(--anim-accent); }}
{A} .{N}-ghost {{ fill: none; }}
/* marks: rings, thin diamonds, dots; no filled boxes */
{A} .{N}-ring {{ fill: var(--anim-bg); stroke: {ink}; stroke-width: 2.5; }}
{A} .{N}-ext {{ stroke-dasharray: 6 6; }}
{A} .{N}-dot {{ fill: var(--anim-bg); stroke: {ink}; stroke-width: 2.5; }}
{A} .{N}-glyph {{ fill: none; stroke: var(--anim-muted); stroke-width: 2.25; stroke-linecap: round; stroke-linejoin: round; }}
{A} .{N}-is-ok {{ fill: none; stroke: var(--anim-ok); }}
{A} .{N}-dot.{N}-is-ok {{ fill: var(--anim-ok); }}
{A} .{N}-is-hl {{ fill: none; stroke: var(--anim-accent); stroke-width: 4; }}
{A} .{N}-dot.{N}-is-hl {{ fill: var(--anim-accent); stroke-width: 2.5; }}
{A} .{N}-in-ok {{ fill: var(--anim-ok); }}
{A} .{N}-in-hl {{ fill: var(--anim-accent); }}
{A} path.{N}-in-ok {{ fill: none; stroke: var(--anim-ok); }}
{A} path.{N}-in-hl {{ fill: none; stroke: var(--anim-accent); }}
{A} .{N}-glow {{ fill: none; stroke: var(--anim-accent); stroke-width: 10; stroke-linecap: round; opacity: 0.3; filter: blur(6px); }}
/* wires: 2.5 px at rest, the active path 4 px accent (lines never glow) */
{A} .{N}-wire {{ fill: none; stroke: {ink}; stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; }}
{A} .{N}-draw {{ stroke-dasharray: 100 120; stroke-dashoffset: 0; }}
{A} .{N}-ek-depends .{N}-wire {{ stroke-dasharray: 10 8; }}
{A} .{N}-ek-event .{N}-wire {{ stroke-dasharray: 3 9; }}
{A} .{N}-ek-data .{N}-wire {{ stroke-width: 2; }}
{A} .{N}-wire-hl {{ fill: none; stroke: var(--anim-accent); stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; }}
{A} .{N}-arrow {{ fill: none; stroke: {ink}; stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; }}
{A} .{N}-pkt {{ fill: var(--anim-accent); stroke: var(--anim-accent); stroke-width: 12; stroke-opacity: 0.3; }}
{A} .{N}-pkt-event {{ fill: var(--anim-warn); stroke: var(--anim-warn); }}
/* structure: hairlines, brackets, axes */
{A} .{N}-rule {{ fill: none; stroke: var(--anim-line); stroke-width: 2; }}
{A} .{N}-bracket {{ fill: none; stroke: var(--anim-line); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }}
{A} .{N}-leader {{ fill: none; stroke: var(--anim-line); stroke-width: 2; }}
{A} .{N}-tag {{ fill: none; stroke: var(--anim-line); stroke-width: 2; }}
{A} .{N}-axis {{ fill: none; stroke: var(--anim-line); stroke-width: {3 if S.arch == 'timeline' else 2}; stroke-linecap: round; }}
{A} .{N}-prog {{ fill: none; stroke: var(--anim-accent); stroke-width: 4; stroke-linecap: round; stroke-dasharray: 100 120; stroke-dashoffset: 0; }}
{A} .{N}-grid {{ fill: none; stroke: var(--anim-muted); stroke-width: 1.5; stroke-dasharray: 2 7; stroke-linecap: round; opacity: 0.4; }}
{A} .{N}-ser {{ fill: none; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }}
{A} .{N}-c0 {{ stroke: var(--anim-accent); }}
{A} .{N}-c1 {{ stroke: var(--anim-muted); stroke-width: 2.5; stroke-dasharray: 10 8; }}
{A} .{N}-c2 {{ stroke: var(--anim-muted); stroke-dasharray: 8 7; }}
{A} .{N}-f0 {{ fill: var(--anim-accent); }}
{A} .{N}-f1, {A} .{N}-f2 {{ fill: var(--anim-muted); }}
{A} .{N}-tip.{N}-f0 {{ stroke: var(--anim-accent); stroke-width: 12; stroke-opacity: 0.3; }}
{A} .{N}-evl {{ fill: none; stroke: var(--anim-muted); stroke-width: 2; stroke-dasharray: 6 7; }}
"""
    out = [rules]
    if S.edges:
        out.append(f'/* ---- edge paths: the one copy packets read (offset-path: var(--...)); keep in step with each wire d ---- */')
        out.append(f'{A} {{\n' + '\n'.join(f'  --{rid[e["id"]]}: path("{path_d(scene["edges"][e["id"]])}");'
                                             for e in S.edges) + '\n}')
    marks = {}
    for i, p in enumerate(S.phases):
        marks[round(T.t[i], 2)] = p['label']
    if T.once:
        marks[round(T.end, 2)] = 'end = resting frame'
        how = ('plays once when the slide becomes current' if S.control == 'once' else
               'the host plays it segment by segment between the data-anim-phases marks')
        out.append(f'/* ---- motion: one pass of {f1(T.end)} s per element, gated on .visible; {how}, '
                   'then holds the 100 % stop (= resting frame) ---- */')
        for el in anim.segs:
            out.append(f'.visible {A} #{el} {{ animation: {el} {f1(T.end)}s linear 1 both; }}')
    else:
        marks[round(T.rst, 2)] = 'reset'
        out.append(f'/* ---- motion: one full-cycle track per element, gated on .visible (cycle {f1(T.end)} s) ---- */')
        for el in anim.segs:
            out.append(f'.visible {A} #{el} {{ animation: {el} {f1(T.end)}s linear infinite; }}')
    for el, segs in anim.segs.items():
        out.append(css_keyframes(el, segs, T, marks, anim.rest(el)))
    out.append(f'@media (prefers-reduced-motion: reduce) {{ {A} * {{ animation: none !important; }} }}')
    return '\n'.join(out)


REFINE = {
    'pipeline': 'step numbers sit in the rings; a feedback arc in --anim-danger or --anim-warn only if the slide says why',
    'graph': 'dim non-active nodes to 60 %; check the crossing report and edge-label spots; glyphs per kind',
    'timeline': 'past milestones settle to --anim-ok, only "now" stays accent; check leaders and era brackets',
    'states': 'single current-state token; error transitions in --anim-danger; label offsets',
    'compare': 'column headers (taken from a one-side group, else Before/After); left dims as right appears',
    'layers': 'layer names (from a one-layer group, else "Layer N"); bands rise 12 px bottom-up; response packet in --anim-ok',
    'chart': 'thresholds as dashed lines, an inline readout, axis titles, a baseline that does not exaggerate',
}


def fonts(S, args):
    rw = args.rendered_width or S.W
    k = max(1.0, args.min_text * S.W / (18 * rw))
    F = {key: math.ceil(v * k * 2) / 2 for key, v in
         dict(title=26, head=24, lbl=24, note=26, sub=18, mono=18, edge=18, num=20).items()}
    F['ring'], F['dot'] = round(34 * k), round(10 * k)      # ring r 34 and timeline dot r 10 at the stage
    return F, k


def try_layout(S, F):
    """Loosest layout that keeps everything inside the viewBox: (frame, scene, overflow list)."""
    fr = frame(S, F)
    levels = ([(lv, md) for md in ('below', 'side', 'small') for lv in range(len(GRAPH_FIT))]
              if S.arch == 'graph' and not S.lanes else [None])
    for lv in levels:
        scene = LAYOUTS[S.arch](S, F, fr[0], fr[1]) if lv is None else layout_graph(S, F, fr[0], fr[1], *lv)
        if S.arch in ('states', 'layers', 'timeline') and 'labels' not in scene:
            scene['labels'] = place_edge_labels(S, F, scene)
        out = outside(S, F, scene, fr)
        if not out:
            break
    if not out and scene.get('mode') == 'small':
        warn('graph: rings shrunk to fit the height; raise size H for full-size rings')
    return fr, scene, out


def fit_layout(S, F, args):
    """Lay out; if something still leaves the viewBox at the tightest spacing, find the smallest
    viewBox (20 px steps) that fits and stop with that size instead of writing a broken file."""
    fr, scene, out = try_layout(S, F)
    if not out:
        return fr, scene
    quiet = globals()['warn']
    globals()['warn'] = lambda msg: None              # trial layouts: no repeated warnings
    try:
        T = Spec()
        T.__dict__.update(S.__dict__)
        while out and T.W <= 6000 and T.H <= 4000:
            ylim = T.H - frame(T, F)[2] - 8 if frame(T, F)[3] else T.H
            wide = any(x0 < 0 or x1 > T.W for _, x0, _, x1, _ in out)
            tall = any(y0 < 0 or y1 > ylim for _, _, y0, _, y1 in out)
            T.W += 20 if wide else 0
            T.H += 20 if tall or not wide else 0
            Ft = fonts(T, argparse.Namespace(**{**vars(args), 'rendered_width': args.rendered_width}))[0]
            out = try_layout(T, Ft)[2]
    finally:
        globals()['warn'] = quiet
    what = '; '.join(f'{w} spans x {x0:.0f}..{x1:.0f}, y {y0:.0f}..{y1:.0f}'
                     for w, x0, y0, x1, y1 in try_layout(S, F)[2][:4])
    die(f'{S.arch} needs at least {T.W}x{T.H} at this label length; pass --viewbox {T.W} {T.H} or shorten labels '
        f'(at {S.W}x{S.H}: {what})')


def main():
    ap = argparse.ArgumentParser(description='Scaffold an anim-slides fragment from a spec.')
    ap.add_argument('spec')
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--viewbox', nargs=2, type=int, metavar=('W', 'H'))
    ap.add_argument('--rendered-width', type=float)
    ap.add_argument('--stage-width', type=float, default=1920)
    ap.add_argument('--min-text', type=float)
    ap.add_argument('--control', choices=['once', 'loop', 'step'])
    ap.add_argument('--no-check', action='store_true')
    args = ap.parse_args()
    if args.min_text is None:
        args.min_text = round(18 * args.stage_width / 1920, 2)

    S = validate(load_spec(args.spec), args)
    rw = args.rendered_width or S.W
    F, k = fonts(S, args)
    if k > 1:
        warn(f'fonts scaled x{k:.2f} to stay >= {args.min_text:g}px at {rw:g}px wide; boxes may need resizing')
    fr, scene = fit_layout(S, F, args)
    if S.arch == 'graph' or S.edges:
        cross, through = edge_report(S, scene)
        if cross or through:
            warn(f'{S.arch}: {len(cross)} edge crossing(s), {len(through)} edge(s) through a node remain '
                 f'({"; ".join(cross + through)}); reorder nodes in the spec (it breaks ordering ties) or reroute by hand')
        else:
            print(f'{S.arch} layout: 0 edge crossings, no edge through a node')
    if scene.get('label_bad'):
        warn(f'edge label(s) on {", ".join(scene["label_bad"])} touch another wire, node or label wherever they '
             'go; move by hand')
    T = Timing(S)
    anim = Anim()
    rid = build_anims(S, T, scene, anim)
    body = emit(S, args, F, scene, T, anim, rid, fr)

    words = ', '.join(n['label'] for n in S.nodes) or ', '.join(s['label'] for s in S.series)
    aria = escape(f'{S.title + ": " if S.title else ""}{S.arch} of {words}', quote=True)
    cyc = f1(T.end)
    refine = ('<!-- scaffold: refine by hand -\n'
              f'  generated by scripts/scaffold_from_spec.py from {os.path.basename(args.spec)} '
              f'({S.arch}, {S.control}, {S.W}x{S.H}, rendered {rw:g}px)\n'
              f'  - {REFINE[S.arch]}\n'
              '  - lean style (references/style.md): rings, hairlines, one accent; glyphs per kind are placeholders\n'
              '  - aria-label: rewrite as one sentence that tells the story\n'
              '  - motion audit (references/motion-rules.md); render-phases.sh and LOOK at every PNG\n'
              f'  - edge paths: each wire keeps its d attribute (SVG d cannot read a CSS variable in every\n'
              f'    browser), and the same path is written ONCE more in <style> as --{S.name}-e-<from>-<to>;\n'
              f'    every packet on that edge uses offset-path: var(--{S.name}-e-<from>-<to>). To reroute an\n'
              f'    edge change its d (and its -hl copy, if any) and that one --{S.name}-e-... line\n-->')
    html = [refine, '<style>', css(S, F, T, anim, scene, rid), '</style>',
            f'<div class="anim anim-{S.name}" data-anim="{S.name}" data-anim-cycle="{cyc}" '
            f'data-anim-phases="{T.marks(S)}" data-anim-control="{S.control}">',
            f'<svg viewBox="0 0 {S.W} {S.H}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" '
            f'role="img" aria-label="{aria}">']
    html += ['  ' + x for x in body]
    html.append('</svg>')
    html.append('</div>')
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(html) + '\n')
    print(f'wrote {args.output}: {S.arch}, {len(S.nodes)} nodes, {len(S.edges)} edges, '
          f'{len(S.phases)} phases, control {S.control}, viewBox {S.W}x{S.H}')
    if args.no_check:
        return
    checker = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'check_fragment.py')
    cmd = [sys.executable, checker, args.output, '--name', S.name, '--rendered-width', f'{rw:g}',
           '--min-text', f'{args.min_text:g}']
    probe = subprocess.run([sys.executable, checker, '--help'], capture_output=True, text=True)
    if '--stage-width' in probe.stdout:          # older checkers only take --min-text
        cmd += ['--stage-width', f'{args.stage_width:g}']
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout, end='')
    if r.returncode:
        sys.exit('scaffold_from_spec: the output fails check_fragment.py (see above)')


if __name__ == '__main__':
    main()
