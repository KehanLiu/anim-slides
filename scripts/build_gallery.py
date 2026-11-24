#!/usr/bin/env python3
"""Build a static gallery site from a pool of anim-slides fragments.

usage:
  build_gallery.py -o DIR [--pool DIR] [--title TEXT] [--repo-url URL]
  build_gallery.py --demo FRAGMENT.html -o OUT.html [--title TEXT] [--story TEXT] [--repo-url URL]
                [--focus 0..1]

Reads <pool>/index.yaml (a plain YAML list of entries; folders without a row are added with
what can be read from the fragment) and writes:

  DIR/index.html          a featured demo first (#featured: one question, the figure playing once
                          in view, a one-line answer, Replay, Copy prompt, Download playable demo,
                          Copy embeddable HTML, Link), then every fragment live in a searchable,
                          filterable grid with a light/dark retheme toggle; a once fragment plays
                          one pass when its card scrolls into view and then rests on its finished
                          state; each card has a Replay button and, when the fragment carries
                          data-anim-phases, a Step button that plays it mark by mark
  DIR/<name>/index.html   one page per fragment: large live view, Download playable demo,
                          Copy embeddable HTML, spec.yaml
  DIR/<name>/<name>.html  the fragment itself, byte-identical to the pool file, plus thumb.png and
                          spec.yaml when present
  DIR/<name>/<name>-demo.html
                          a standalone playable page around the unchanged fragment (demo_page()):
                          no network loads, plays once on open, Replay button, resting frame under
                          prefers-reduced-motion and in print

--demo wraps any fragment file the same way, outside the pool.

All fragments share the index page, so the build checks that every class, id and keyframe is
prefixed with the fragment name and that no two fragments collide; a collision is an error.
Stdlib only, Python 3.9+. No external JS; gallery fonts come from Google Fonts with local
fallbacks (the demo pages use system fonts only).
"""
import argparse
import html
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_POOL = os.path.join(os.path.dirname(HERE), 'pool')
NAME_RE = re.compile(r'^[a-z][a-z0-9-]*$')
DEFAULT_REPO = 'https://github.com/KehanLiu/anim-slides'

# The featured demo at the top of the index. The answer states only what the fragment shows:
# its last caption reads "Provider down: only Payments degrades, orders keep flowing", Payments
# is marked DEGRADED inside the "blast radius" outline, and web app, gateway, Orders, Orders DB
# and event bus are lit as healthy. The figure does not show whether those orders get paid.
FEATURED = {
    'name': 'service-deps',
    # where a narrow screen's scroll frame opens (fraction of the figure width): the centre of the
    # "blast radius" outline, viewBox x 696..1524 of 1680 (path x 720..1640 in the group scaled .9
    # and moved 48); an index.yaml "focus" key for the entry wins over this value
    'focus': 0.66,
    'question': 'When the payment provider goes down, can orders still go through?',
    'answer': ('Yes, in this system. The outage reaches only Payments, which degrades; the API gateway, '
               'Orders, Orders DB and event bus stay healthy, so orders keep flowing.'),
    'prompt': ('Use anim-slides to draw my services and their dependencies as one animated diagram for a '
               'slide. Then show what an outage of <DEPENDENCY> reaches: which services fail or degrade, '
               'and which keep working. Label only what is in my list.\n'
               'My services and what each one calls:\n'
               '<SERVICE LIST, e.g. web app -> API gateway; API gateway -> Orders, Payments; '
               'Payments -> payment provider (third party)>'),
}


def die(msg):
    sys.exit(f'build_gallery: error: {msg}')


def warn(msg):
    print(f'build_gallery: warning: {msg}', file=sys.stderr)


# --------------------------------------------------------------------------- index.yaml
def _scalar(tok):
    tok = tok.strip()
    if tok in ('', '~', 'null'):
        return None
    if tok in ('true', 'True'):
        return True
    if tok in ('false', 'False'):
        return False
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in '"\'':
        return tok[1:-1]
    if re.fullmatch(r'[-+]?\d+', tok):
        return int(tok)
    if re.fullmatch(r'[-+]?\d*\.\d+', tok):
        return float(tok)
    return tok


def _split_flow(src):
    """Split the inside of [a, "b, c", d] at top-level commas."""
    out, buf, q = [], [], None
    for ch in src:
        if q:
            buf.append(ch)
            if ch == q:
                q = None
        elif ch in '"\'':
            q = ch
            buf.append(ch)
        elif ch == ',':
            out.append(''.join(buf))
            buf = []
        else:
            buf.append(ch)
    if ''.join(buf).strip():
        out.append(''.join(buf))
    return [_scalar(t) for t in out]


def _strip_comment(line):
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


def read_index(path):
    """The index.yaml subset: a top-level list of flat mappings whose values are scalars or
    one-line flow lists ([a, b]). Anything richer is a parse error with its line number."""
    entries, cur = [], None
    with open(path, encoding='utf-8') as f:
        for no, raw in enumerate(f, 1):
            line = _strip_comment(raw.rstrip('\n')).rstrip()
            if not line.strip() or line.startswith('---'):
                continue
            body = line.strip()
            if body.startswith('- '):
                cur = {}
                entries.append(cur)
                body = body[2:].strip()
            elif cur is None:
                die(f'{path}:{no}: expected a list item ("- name: ...")')
            m = re.match(r'([A-Za-z_][\w-]*)\s*:(?:\s+(.*))?$', body)
            if not m:
                die(f'{path}:{no}: expected "key: value", got {body!r}')
            key, val = m.group(1), (m.group(2) or '').strip()
            if val.startswith('['):
                if not val.endswith(']'):
                    die(f'{path}:{no}: flow lists must close on the same line')
                cur[key] = _split_flow(val[1:-1])
            else:
                cur[key] = _scalar(val)
    return entries


# --------------------------------------------------------------------------- fragments
def viewbox_of(src):
    m = re.search(r'<svg\b[^>]*\bviewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', src)
    return [float(m.group(1)), float(m.group(2))] if m else [1600, 900]


def check_prefixes(name, src):
    """Return (problems, names) where names is the set of class/id/keyframe names it defines."""
    problems, names = [], set()
    allowed = {'anim', f'anim-{name}', 'visible'}
    for cls in re.findall(r'\bclass="([^"]*)"', src):
        for c in cls.split():
            names.add(('class', c))
            if c not in allowed and not c.startswith(f'{name}-'):
                problems.append(f'class "{c}" is not prefixed with "{name}-"')
    for i in re.findall(r'\bid="([^"]*)"', src):
        names.add(('id', i))
        if not i.startswith(f'{name}-'):
            problems.append(f'id "{i}" is not prefixed with "{name}-"')
    for k in re.findall(r'@keyframes\s+([\w-]+)', src):
        names.add(('keyframes', k))
        if not (k == name or k.startswith(f'{name}-')):
            problems.append(f'keyframes "{k}" is not prefixed with "{name}"')
    return sorted(set(problems)), names - {('class', 'anim'), ('class', 'visible')}


def focus_of(val, default=None, name=''):
    """The scroll-frame focus: a number 0..1 (fraction of the figure width), else default/0.5."""
    for v in (val, default):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if 0 <= v <= 1:
                return float(v)
            warn(f'{name}: focus {v!r} is outside 0..1; ignored')
    return 0.5


def load_pool(pool):
    if not os.path.isdir(pool):
        die(f'pool folder not found: {pool}')
    idx = os.path.join(pool, 'index.yaml')
    rows = read_index(idx) if os.path.isfile(idx) else []
    by_name = {}
    for r in rows:
        n = r.get('name')
        if not isinstance(n, str) or not NAME_RE.match(n):
            warn(f'index.yaml: skipping an entry with a missing or invalid name: {n!r}')
            continue
        if n in by_name:
            die(f'index.yaml: duplicate entry "{n}"')
        by_name[n] = r
    for d in sorted(os.listdir(pool)):                     # folders without an index row
        if d not in by_name and os.path.isfile(os.path.join(pool, d, f'{d}.html')):
            if rows:
                warn(f'{d}/ has no row in index.yaml; adding it with defaults')
            by_name[d] = {'name': d}

    entries = []
    for n, r in by_name.items():
        frag = os.path.join(pool, n, f'{n}.html')
        if not os.path.isfile(frag):
            warn(f'{n}: {n}/{n}.html not found; skipped')
            continue
        src = open(frag, encoding='utf-8').read()
        e = dict(r)
        e['src'] = src
        e['dir'] = os.path.join(pool, n)
        vb = r.get('viewbox')
        e['viewbox'] = [float(v) for v in vb] if isinstance(vb, list) and len(vb) == 2 else viewbox_of(src)
        m = re.search(r'data-anim-cycle="([\d.]+)"', src)     # the fragment is the truth
        e['cycle'] = _scalar(m.group(1)) if m else e.get('cycle')
        m = re.search(r'data-anim-control="(\w+)"', src)
        e['control'] = m.group(1) if m else 'once'
        m = re.search(r'data-anim-phases="([\d.,\s]+)"', src)
        e['phases'] = ','.join(x.strip() for x in m.group(1).split(',') if x.strip()) if m else ''
        e['focus'] = focus_of(e.get('focus'), FEATURED.get('focus') if n == FEATURED['name'] else None, n)
        e['archetype'] = e.get('archetype') or 'other'
        e['tags'] = [str(t) for t in (e.get('tags') or [])]
        spec = os.path.join(pool, n, 'spec.yaml')
        e['spec_text'] = open(spec, encoding='utf-8').read() if os.path.isfile(spec) else None
        e['thumb'] = os.path.isfile(os.path.join(pool, n, 'thumb.png'))
        entries.append(e)
    if not entries:
        die(f'no fragments found in {pool} (expected <name>/<name>.html)')

    owner, errors = {}, []
    for e in entries:
        problems, names = check_prefixes(e['name'], e['src'])
        for p in problems:
            warn(f"{e['name']}: {p}")
        for key in names:
            if key in owner and owner[key] != e['name']:
                errors.append(f'{key[0]} "{key[1]}" is defined by both {owner[key]} and {e["name"]}')
            owner.setdefault(key, e['name'])
    if errors:
        die('fragments collide on the shared index page:\n  ' + '\n  '.join(errors))
    return entries


# --------------------------------------------------------------------------- page chrome
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700'
         '&family=JetBrains+Mono:wght@400;500&display=swap">')

CSS = r"""
:root{
  --anim-theme-bg:#0F1E27;--anim-theme-panel:#0D1820;--anim-theme-line:#2A3D49;
  --anim-theme-fg:#E6EDF0;--anim-theme-muted:#93A7B2;--anim-theme-accent:#34D1BF;
  --anim-theme-accent-2:#FF8A3D;--anim-theme-ok:#8ED7AD;--anim-theme-warn:#FFD15C;
  --anim-theme-danger:#FF6B6B;
  --page:#0a0d12;--card:#131823;--border:#252d3d;--text:#e8edf5;--muted:#93a0b6;--link:#34D1BF;
  --chip:#1a2130;--chip-on:#34D1BF;--chip-on-text:#06121c;
  --ui:'Inter',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
  --code:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  color-scheme:dark;
}
:root[data-theme="light"]{
  --anim-theme-bg:#ffffff;--anim-theme-panel:#f2f4f8;--anim-theme-line:#c5ccd8;
  --anim-theme-fg:#14181f;--anim-theme-muted:#5b6474;--anim-theme-accent:#0a6cff;
  --anim-theme-accent-2:#d9480f;--anim-theme-ok:#2b8a3e;--anim-theme-warn:#e67700;
  --anim-theme-danger:#c92a2a;
  --page:#eef1f6;--card:#ffffff;--border:#d9dee8;--text:#14181f;--muted:#5b6474;--link:#0a6cff;
  --chip:#ffffff;--chip-on:#0a6cff;--chip-on-text:#ffffff;
  color-scheme:light;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--page);color:var(--text);font:15px/1.5 var(--ui)}
a{color:var(--link);text-decoration:none}
a:hover{text-decoration:underline}
code,pre{font-family:var(--code)}
.wrap{max-width:1640px;margin:0 auto;padding:0 16px}
header.top{border-bottom:1px solid var(--border);position:sticky;top:0;z-index:5;
  background:color-mix(in srgb,var(--page) 88%,transparent);backdrop-filter:blur(8px)}
header.top .wrap{display:flex;align-items:center;gap:12px;min-height:56px}
.brand{font-weight:700;font-size:17px;color:var(--text);letter-spacing:-.01em;white-space:nowrap}
.brand span{color:var(--anim-theme-accent)}
.spacer{flex:1}
.btn{font:inherit;font-size:13px;font-weight:500;color:var(--text);background:var(--chip);
  border:1px solid var(--border);border-radius:8px;padding:6px 12px;cursor:pointer;white-space:nowrap}
.btn:hover{border-color:var(--muted)}
.btn.primary{background:var(--chip-on);color:var(--chip-on-text);border-color:var(--chip-on)}
.hero{padding:40px 0 8px}
.hero h1{font-size:clamp(26px,4vw,40px);line-height:1.15;letter-spacing:-.02em;margin:0 0 10px}
.hero p{color:var(--muted);max-width:760px;margin:0 0 14px;font-size:16px}
.install{display:inline-flex;align-items:center;gap:8px;max-width:100%;background:var(--card);
  border:1px solid var(--border);border-radius:8px;padding:6px 6px 6px 12px}
.install code{font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.filters{display:flex;flex-direction:column;gap:8px;padding:20px 0 4px}
.frow{display:flex;flex-wrap:wrap;align-items:center;gap:6px}
.frow .lbl{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);width:84px}
.chip{font:inherit;font-size:13px;color:var(--text);background:var(--chip);border:1px solid var(--border);
  border-radius:999px;padding:3px 11px;cursor:pointer}
.chip[aria-pressed="true"]{background:var(--chip-on);color:var(--chip-on-text);border-color:var(--chip-on)}
.search{font:inherit;font-size:14px;color:var(--text);background:var(--chip);border:1px solid var(--border);
  border-radius:8px;padding:6px 10px;width:260px;max-width:100%}
.count{font-size:13px;color:var(--muted);margin:10px 0 0}
.grid{display:grid;align-items:start;grid-template-columns:repeat(auto-fill,minmax(min(500px,100%),1fr));gap:18px;padding:12px 0 40px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;
  display:flex;flex-direction:column;min-width:0}
.card[hidden]{display:none}
.stage{display:block;background:var(--anim-theme-bg);padding:12px;border-bottom:1px solid var(--border);overflow:hidden}
.stage>.fit{width:100%}
/* loop fragments only: start part-way into the loop so the grid looks alive at first sight;
   fragments set no delays of their own, so one shifted delay keeps their internal timing intact.
   once fragments start at 0 s when their card scrolls into view and then rest. */
.lead *{animation-delay:var(--lead,0s) !important}
.card .body{padding:12px 14px 14px;display:flex;flex-direction:column;gap:6px;flex:1}
.card h2{font-size:16px;margin:0;font-family:var(--code);font-weight:500;display:flex;align-items:center;gap:8px}
.card h2 .acts{margin-left:auto;display:flex;gap:6px}
.card h2 .btn{font-family:var(--sans,inherit);font-size:12px;padding:2px 9px}
.card h2 a{color:var(--text)}
.meta{display:flex;flex-wrap:wrap;gap:6px;font-size:12px}
.pill{border-radius:6px;padding:1px 7px;background:color-mix(in srgb,var(--anim-theme-accent) 16%,transparent);
  color:var(--text);border:1px solid color-mix(in srgb,var(--anim-theme-accent) 40%,transparent)}
.pill.dom{background:color-mix(in srgb,var(--anim-theme-ok) 16%,transparent);
  border-color:color-mix(in srgb,var(--anim-theme-ok) 40%,transparent)}
.pill.dim{background:none;border-color:var(--border);color:var(--muted)}
.story{color:var(--muted);font-size:14px;margin:0}
.tags{display:flex;flex-wrap:wrap;gap:4px 8px;font-size:12px;color:var(--muted);font-family:var(--code);margin-top:auto}
.empty{color:var(--muted);padding:40px 0;text-align:center}
footer{border-top:1px solid var(--border);color:var(--muted);font-size:13px;padding:20px 0 32px}
.crumbs{padding:24px 0 6px;font-size:14px;color:var(--muted)}
.detail h1{font-family:var(--code);font-weight:500;font-size:clamp(22px,3vw,30px);margin:0 0 8px}
.detail .story{font-size:16px;max-width:900px}
.bigstage{background:var(--anim-theme-bg);border:1px solid var(--border);border-radius:12px;padding:16px;margin:18px 0}
.bigstage>.fit{margin:0 auto}
.actions{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 18px}
dl.facts{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;font-size:14px;margin:0 0 24px}
dl.facts dt{color:var(--muted)}
dl.facts dd{margin:0}
h3{font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:24px 0 8px}
pre.src{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px;
  overflow:auto;font-size:12.5px;line-height:1.55;max-height:560px;margin:0 0 32px;tab-size:2}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:var(--chip-on);
  color:var(--chip-on-text);padding:8px 14px;border-radius:8px;font-size:14px;opacity:0;
  transition:opacity .2s;pointer-events:none}
.toast.on{opacity:1}
/* featured demo: the figure sits on the page ground (no box), one question, one answer */
.feature{--anim-theme-bg:var(--page);padding:36px 0 32px;border-bottom:1px solid var(--border);scroll-margin-top:64px}
.kicker{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 12px}
.feature h1{font-size:clamp(26px,3.6vw,46px);line-height:1.12;letter-spacing:-.02em;margin:0 0 6px;max-width:21em;text-wrap:balance}
.scroll{overflow-x:auto;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch}
.feature .fit{margin:0 auto}
.swipe{display:none;font-size:13px;color:var(--muted);margin:4px 0 0}
.answer{font-size:clamp(18px,1.7vw,22px);line-height:1.45;max-width:44em;margin:14px 0 20px;text-wrap:pretty}
.answer b{color:var(--anim-theme-accent);font-weight:600}
.feature .actions,.detail .actions{gap:10px}
.feature .actions .btn,.detail .actions .btn{font-size:14px;padding:9px 15px;min-height:42px;display:inline-flex;align-items:center}
.prompt{margin:4px 0 0;max-width:60em;color:var(--muted);font-size:14px}
.prompt pre{white-space:pre-wrap;font-size:13px;line-height:1.55;color:var(--text);margin:6px 0 0;
  padding:0 0 0 14px;border-left:2px solid var(--border)}
.how{color:var(--muted);font-size:14px;max-width:60em;margin:18px 0 0}
.hero h2{font-size:clamp(22px,2.6vw,30px);line-height:1.2;letter-spacing:-.01em;margin:0 0 10px}
/* a figure wider than the screen scrolls inside a full-bleed frame; a soft fade on each clipped
   edge (a mask, so it works on either ground) says "more this way" */
.scroll{--fl:0px;--fr:0px;-webkit-mask-image:linear-gradient(to right,transparent,#000 var(--fl),#000 calc(100% - var(--fr)),transparent);
  mask-image:linear-gradient(to right,transparent,#000 var(--fl),#000 calc(100% - var(--fr)),transparent)}
.scroll.fl{--fl:16px}.scroll.fr{--fr:16px}
@media (max-width:760px){
  .scroll{margin:0 -16px}
  .scroll>.fit{min-width:740px;max-width:none !important}
  .bigstage{margin:12px -16px;padding:8px 0;border-radius:0;border-left:0;border-right:0}
  .bigstage .scroll{margin:0}
  .bigstage .swipe{padding:0 16px}
  .swipe{display:block}
  .feature .actions .btn,.detail .actions .btn{min-height:44px}
  .search{width:100%}
}
@media print{.scroll{margin:0;overflow:visible;-webkit-mask-image:none;mask-image:none}
  .scroll>.fit{min-width:0 !important}.swipe{display:none !important}}
@media (max-width:640px){
  .hero{padding:24px 0 4px}
  .frow .lbl{width:100%}
  header.top .brand small{display:none}
  header.top .btn{padding:6px 9px}
  .grid{gap:14px}
  .stage{padding:6px}
}
"""

# Theme toggle, live-in-view gating, filters, copy. Inline, no dependencies.
JS = r"""
(function(){
  var root=document.documentElement;
  function setTheme(t){root.setAttribute('data-theme',t);
    var b=document.getElementById('theme');if(b)b.textContent=t==='light'?'Dark theme':'Light theme';
    try{localStorage.setItem('anim-gallery-theme',t)}catch(e){}}
  var saved=null;try{saved=localStorage.getItem('anim-gallery-theme')}catch(e){}
  setTheme(saved||'dark');
  document.addEventListener('click',function(ev){
    var t=ev.target.closest('button');if(!t)return;
    if(t.id==='theme')setTheme(root.getAttribute('data-theme')==='light'?'dark':'light');
    if(t.id==='rest'){var on=t.getAttribute('aria-pressed')!=='true';t.setAttribute('aria-pressed',on);
      root.classList.toggle('resting',on);t.textContent=on?'Play animations':'Show resting frames';
      document.querySelectorAll('.fit').forEach(function(f){unstep(f);gate(f,!on&&f._inview!==false)})}
    if(t.dataset.replay){var f=document.getElementById(t.dataset.replay);unstep(f);gate(f,false);
      void f.offsetWidth;gate(f,!root.classList.contains('resting'));if(f)focus(f.parentNode)}
    if(t.dataset.step)step(document.getElementById(t.dataset.step),t);
    if(t.dataset.copy)copy(document.getElementById(t.dataset.copy).value,t.dataset.msg||'Copied');
    if(t.dataset.copylink)copy(location.href.split('#')[0]+'#'+t.dataset.copylink,'Link copied');
    if(t.classList.contains('chip')){var g=t.dataset.group;
      document.querySelectorAll('.chip[data-group="'+g+'"]').forEach(function(c){c.setAttribute('aria-pressed',c===t)});
      filter()}
  });
  function copy(src,msg){var done=function(){toast(msg)};
    if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(src).then(done,fallback)}else fallback();
    function fallback(){var ta=document.createElement('textarea');ta.value=src;document.body.appendChild(ta);
      ta.select();try{document.execCommand('copy');done()}catch(e){toast('Copy failed')}ta.remove()}}
  function gate(f,on){if(f)f.classList.toggle('visible',on)}
  // a figure wider than a phone scrolls inside its frame: open it centred on the entry's focus
  // (data-focus, a fraction of the figure width) and fade only the edges that are clipped
  function fade(s){var m=s.scrollWidth-s.clientWidth;s.classList.toggle('fl',m>1&&s.scrollLeft>1);
    s.classList.toggle('fr',m>1&&s.scrollLeft<m-1)}
  function focus(s){if(!s||!s.classList||!s.classList.contains('scroll'))return;var m=s.scrollWidth-s.clientWidth;
    if(m>1){var k=parseFloat(s.dataset.focus);if(!(k>=0&&k<=1))k=.5;
      s.scrollLeft=Math.max(0,Math.min(m,k*s.scrollWidth-s.clientWidth/2))}fade(s)}
  // a link to #featured scrolls to the featured block and plays its figure from the start
  function featured(){if(location.hash!=='#featured')return;var s=document.getElementById('featured'),
    f=document.getElementById('fit-featured');if(!s||!f)return;s.scrollIntoView({block:'start'});unstep(f);
    gate(f,false);void f.offsetWidth;gate(f,!root.classList.contains('resting'));f._played=true;focus(f.parentNode)}
  window.addEventListener('hashchange',featured);
  // Step: drive the card's CSS animations by its data-anim-phases marks, as a step-mode host does.
  // The first click pauses everything at 0; each click plays to the next mark and pauses there;
  // after the last mark the next click goes back to 0. Replay and the resting toggle leave step mode.
  function anims(f){return f&&f.getAnimations?f.getAnimations({subtree:true}):[]}
  function seek(f,s,play){anims(f).forEach(function(a){a.pause();a.currentTime=s*1000;if(play)a.play()})}
  function unstep(f){if(!f)return;clearTimeout(f._stepT);f._step=null;
    var b=document.querySelector('[data-step="'+f.id+'"]');if(b)b.textContent='Step'}
  function step(f,b){if(!f)return;
    var m=(f.dataset.phases||'').split(',').map(Number).filter(function(x){return x>0});if(!m.length)return;
    clearTimeout(f._stepT);
    if(f._step==null||f._step>=m.length){root.classList.remove('resting');
      var r=document.getElementById('rest');if(r){r.setAttribute('aria-pressed','false');r.textContent='Show resting frames'}
      gate(f,false);void f.offsetWidth;gate(f,true);f._played=true;seek(f,0,false);f._step=0}
    else{var from=f._step?m[f._step-1]:0,to=m[f._step];f._step++;seek(f,from,true);
      f._stepT=setTimeout(function(){seek(f,to,false)},(to-from)*1000)}
    b.textContent='Step '+f._step+'/'+m.length}
  function toast(msg){var el=document.getElementById('toast');if(!el)return;el.textContent=msg;
    el.classList.add('on');clearTimeout(el._t);el._t=setTimeout(function(){el.classList.remove('on')},1600)}
  // play only what is on screen: the fragments are gated on a .visible ancestor. A once fragment
  // plays its single pass the first time it scrolls into view, then keeps the gate so it rests on
  // its finished state; Replay restarts it. Loop fragments run only while on screen.
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(e){var f=e.target;f._inview=e.isIntersecting;
      if(f.dataset.ctl!=='loop'&&!e.isIntersecting&&f._played)return;
      var on=e.isIntersecting&&!root.classList.contains('resting');gate(f,on);if(on)f._played=true})},{rootMargin:'0px'});
    document.querySelectorAll('.fit').forEach(function(f){io.observe(f)});
  }
  var q=document.getElementById('q');if(q)q.addEventListener('input',filter);
  function picked(g){var c=document.querySelector('.chip[data-group="'+g+'"][aria-pressed="true"]');return c?c.dataset.value:''}
  function filter(){var v=picked('verb'),a=picked('archetype'),d=picked('domain'),s=(q&&q.value||'').toLowerCase().trim(),n=0;
    document.querySelectorAll('.card').forEach(function(c){
      var ok=(!v||c.dataset.verb===v)&&(!a||c.dataset.archetype===a)&&(!d||c.dataset.domain===d)&&(!s||c.dataset.text.indexOf(s)>=0);
      c.hidden=!ok;if(ok)n++});
    var k=document.getElementById('count');if(k)k.textContent=n+(n===1?' fragment':' fragments');
    var em=document.getElementById('empty');if(em)em.hidden=n>0}
  document.querySelectorAll('.scroll').forEach(function(s){focus(s);s.addEventListener('scroll',function(){fade(s)},{passive:true})});
  window.addEventListener('resize',function(){document.querySelectorAll('.scroll').forEach(focus)});
  featured();
})();
"""


def esc(s):
    return html.escape(str(s), quote=True)


def fit_style(e, max_h=None):
    w, h = e['viewbox']
    s = f'aspect-ratio:{w:g}/{h:g}'
    if max_h:
        s += f';max-width:min(100%,calc({max_h} * {w / h:.4f}))'
    return s


def page(title, body, desc, depth=0):
    up = '../' * depth
    return f"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="color-scheme" content="dark light">
{FONTS}
<style>{CSS}</style>
</head>
<body>
<header class="top"><div class="wrap">
  <a class="brand" href="{up}index.html">anim<span>-</span>slides <small style="font-weight:400;color:var(--muted)">gallery</small></a>
  <div class="spacer"></div>
  <button class="btn" id="rest" type="button" aria-pressed="false">Show resting frames</button>
  <button class="btn" id="theme" type="button">Light theme</button>
</div></header>
{body}
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<script>{JS}</script>
</body>
</html>
"""


def meta_pills(e):
    out = [f'<span class="pill">{esc(e["verb"])}</span>'] if e.get('verb') else []
    out.append(f'<span class="pill">{esc(e["archetype"])}</span>')
    if e.get('domain'):
        out.append(f'<span class="pill dom">{esc(e["domain"])}</span>')
    w, h = e['viewbox']
    out.append(f'<span class="pill dim">{w:g}×{h:g}</span>')
    if e.get('cycle'):
        c = f'{e["cycle"]:g}' if isinstance(e['cycle'], (int, float)) else esc(e['cycle'])
        out.append(f'<span class="pill dim">{esc(e.get("control") or "once")} {c} s</span>')
    return ''.join(out)


def chips(group, label, values):
    if len(values) < 2:
        return ''
    b = [f'<button class="chip" type="button" data-group="{group}" data-value="" aria-pressed="true">All</button>']
    for v in values:
        b.append(f'<button class="chip" type="button" data-group="{group}" data-value="{esc(v)}" '
                 f'aria-pressed="false">{esc(v)}</button>')
    return f'<div class="frow" role="group" aria-label="{label}"><span class="lbl">{label}</span>{"".join(b)}</div>'


def featured_block(entries, repo_url, feat=FEATURED):
    """The featured demo (#featured): question, the live figure, the answer in words, actions."""
    e = next((x for x in entries if x['name'] == feat['name']), None)
    if e is None:
        warn(f"featured entry {feat['name']} is not in the pool; no featured block")
        return ''
    n = e['name']
    if re.search(r'\bid="', e['src']):
        warn(f'{n}: the featured fragment defines ids; they appear twice on the index page')
    yes, _, rest = feat['answer'].partition(' ')
    spec = (f' (<a href="{n}/spec.yaml">spec.yaml</a>)' if e['spec_text'] is not None else '')
    return f"""<section class="feature" id="featured" aria-labelledby="featured-q">
  <p class="kicker">anim-slides · animated diagrams for your slides, drawn by your coding agent</p>
  <h1 id="featured-q">{esc(feat['question'])}</h1>
  <div class="scroll" data-focus="{e['focus']:g}"><div class="fit visible" id="fit-featured" data-ctl="{esc(e['control'])}" data-phases="{esc(e['phases'])}" style="{fit_style(e, '52vh')}">
{e['src']}
  </div></div>
  <p class="swipe">Swipe sideways to see the whole figure.</p>
  <p class="answer"><b>{esc(yes)}</b> {esc(rest)}</p>
  <div class="actions">
    <button class="btn" type="button" data-replay="fit-featured">Replay</button>
    <button class="btn primary" type="button" data-copy="prompt-featured" data-msg="Prompt copied">Copy prompt</button>
    <a class="btn" href="{n}/{n}-demo.html" download>Download playable demo</a>
    <button class="btn" type="button" data-copy="src-featured" data-msg="Embeddable HTML copied">Copy embeddable HTML</button>
    <button class="btn" type="button" data-copylink="featured" aria-label="Copy a link to this demo">Link</button>
  </div>
  <textarea class="sr" id="prompt-featured" aria-hidden="true" tabindex="-1">{esc(feat['prompt'])}</textarea>
  <textarea class="sr" id="src-featured" aria-hidden="true" tabindex="-1">{esc(e['src'])}</textarea>
  <div class="prompt">Try it on your own architecture: paste this into your coding agent with the skill installed.
    <pre>{esc(feat['prompt'])}</pre></div>
  <p class="how">What the skill made: one inline <code>&lt;svg&gt;</code> with CSS keyframes and no script,
  from a short spec of eight services and their calls{spec}. It plays once and rests on the finished
  frame, so it also prints. <a href="{n}/index.html">Details</a></p>
</section>"""


def build_index(entries, title, repo_url):
    archetypes = sorted({e['archetype'] for e in entries})
    verbs = sorted({str(e['verb']) for e in entries if e.get('verb')})
    domains = sorted({str(e['domain']) for e in entries if e.get('domain')})
    cards = []
    for e in entries:
        n = e['name']
        text = ' '.join([n, str(e.get('verb') or ''), e['archetype'], str(e.get('domain') or ''), str(e.get('story') or ''), *e['tags']]).lower()
        tags = ''.join(f'<span>#{esc(t)}</span>' for t in e['tags'])
        cyc = e.get('cycle')
        if e['control'] == 'loop' and isinstance(cyc, (int, float)) and cyc > 0 and 'animation-delay' not in e['src']:
            lead_cls, lead = ' lead', f';--lead:-{0.4 * cyc:.2f}s'
        else:
            lead_cls, lead = '', ''
        step_btn = (f'<button class="btn" type="button" data-step="fit-{n}" aria-label="Step through {esc(n)} '
                    f'phase by phase">Step</button>' if e['phases'] else '')
        cards.append(f"""<article class="card" data-verb="{esc(e.get('verb') or '')}" data-archetype="{esc(e['archetype'])}" data-domain="{esc(e.get('domain') or '')}" data-text="{esc(text)}">
  <a class="stage" href="{n}/index.html" aria-label="Open {esc(n)}"><div class="fit visible{lead_cls}" id="fit-{n}" data-ctl="{esc(e['control'])}" data-phases="{esc(e['phases'])}" style="{fit_style(e)}{lead}">
{e['src']}
  </div></a>
  <div class="body">
    <h2><a href="{n}/index.html">{esc(n)}</a><span class="acts">{step_btn}<button class="btn" type="button" data-replay="fit-{n}" aria-label="Replay {esc(n)}">Replay</button></span></h2>
    <div class="meta">{meta_pills(e)}</div>
    <p class="story">{esc(e.get('story') or '')}</p>
    <div class="tags">{tags}</div>
  </div>
</article>""")
    install = ''
    if repo_url and 'github.com/' in repo_url:
        slug = repo_url.rstrip('/').split('github.com/')[1]
        install = (f'<div class="install"><code id="inst">npx skills add {esc(slug)}</code>'
                   f'<textarea class="sr" id="inst-src" aria-hidden="true" tabindex="-1">npx skills add {esc(slug)}</textarea>'
                   f'<button class="btn" type="button" data-copy="inst-src">Copy</button></div>')
    src_link = f' <a href="{esc(repo_url)}">Source on GitHub</a>.' if repo_url else ''
    body = f"""<main class="wrap">
{featured_block(entries, repo_url)}
<section class="hero">
  <h2>{esc(title)}</h2>
  <p>Every fragment below is live: one self-contained <code>&lt;style&gt;</code> plus one inline
  <code>&lt;svg&gt;</code>, CSS keyframes only, prefixed so they all share this page. The theme
  button rethemes all of them through <code>--anim-theme-*</code> variables.{src_link}</p>
  {install}
</section>
<section class="filters" aria-label="Filters">
  {chips('verb', 'Verb', verbs)}
  {chips('archetype', 'Archetype', archetypes)}
  {chips('domain', 'Domain', domains)}
  <div class="frow"><span class="lbl">Search</span><input class="search" id="q" type="search" placeholder="name, story, tag, domain or verb" aria-label="Search fragments"></div>
  <p class="count" id="count">{len(entries)} fragments</p>
</section>
<section class="grid">
{chr(10).join(cards)}
</section>
<p class="empty" id="empty" hidden>No fragment matches these filters.</p>
</main>
<footer><div class="wrap">Built by <code>scripts/build_gallery.py</code>. Fragments are MIT licensed;
adapt them, do not ship their example stories unchanged.</div></footer>"""
    return page(title, body, f'{len(entries)} animated SVG fragments for HTML slide decks')


def build_detail(e, title, repo_url):
    n = e['name']
    w, h = e['viewbox']
    facts = [('Verb', esc(e['verb']))] if e.get('verb') else []
    facts.append(('Archetype', esc(e['archetype'])))
    if e.get('domain'):
        facts.append(('Domain', esc(e['domain'])))
    facts.append(('viewBox', f'{w:g} × {h:g}'))
    facts.append(('Control', {'once': 'once: plays one pass, then rests on the finished state',
                              'loop': 'loop: repeats while shown', 'step': 'step: presenter-driven'}
                  .get(e.get('control'), esc(e.get('control') or ''))))
    if e.get('cycle'):
        facts.append(('Pass' if e.get('control') != 'loop' else 'Cycle', f'{esc(e["cycle"])} s'))
    if e.get('technique'):
        facts.append(('Technique', esc(e['technique'])))
    if e['tags']:
        facts.append(('Tags', ', '.join(esc(t) for t in e['tags'])))
    files = [f'<a href="{n}.html" download>{n}.html</a> (fragment)',
             f'<a href="{n}-demo.html" download>{n}-demo.html</a> (playable page)']
    if e['spec_text'] is not None:
        files.append(f'<a href="spec.yaml" download>spec.yaml</a>')
    if e['thumb']:
        files.append(f'<a href="thumb.png">thumb.png</a>')
    facts.append(('Files', ' · '.join(files)))
    if repo_url:
        facts.append(('Source', f'<a href="{esc(repo_url.rstrip("/"))}/tree/main/pool/{n}">pool/{n}/</a>'))
    dl = ''.join(f'<dt>{k}</dt><dd>{v}</dd>' for k, v in facts)
    spec = (f'<h3>spec.yaml</h3><pre class="src"><code>{esc(e["spec_text"])}</code></pre>'
            if e['spec_text'] is not None else '')
    body = f"""<main class="wrap detail">
<nav class="crumbs"><a href="../index.html">All fragments</a> / {esc(n)}</nav>
<h1>{esc(n)}</h1>
<p class="story">{esc(e.get('story') or '')}</p>
<div class="bigstage"><div class="scroll" data-focus="{e['focus']:g}"><div class="fit visible" id="live" data-ctl="{esc(e['control'])}" data-phases="{esc(e['phases'])}" style="{fit_style(e, '72vh')}">
{e['src']}
</div></div><p class="swipe">Swipe sideways to see the whole figure.</p></div>
<div class="actions">
  <button class="btn" type="button" data-replay="live">Replay</button>
  {'<button class="btn" type="button" data-step="live">Step</button>' if e['phases'] else ''}
  <a class="btn primary" href="{n}-demo.html" download>Download playable demo</a>
  <button class="btn" type="button" data-copy="frag-src" data-msg="Embeddable HTML copied">Copy embeddable HTML</button>
</div>
<textarea class="sr" id="frag-src" aria-hidden="true" tabindex="-1">{esc(e['src'])}</textarea>
<dl class="facts">{dl}</dl>
<p class="story" style="font-size:14px">Paste the fragment into any HTML deck; it plays while an ancestor has the
class <code>visible</code> (one pass for <code>once</code>, then it holds the finished state) and
otherwise shows its resting frame. Rename the prefix
(<code>{esc(n)}</code>) when you adapt it so it stays unique in your deck.</p>
{spec}
</main>"""
    return page(f'{n} · {title}', body, str(e.get('story') or n), depth=1)


# --------------------------------------------------------------------------- playable demo page
# A standalone page around one unchanged fragment. No network loads (system fonts, inline CSS and
# JS). The script adds the fragment's gate class (.visible) on open, so a once fragment plays one
# pass and rests on its finished frame; Replay drops the gate, forces a reflow, sets it again and
# rewinds the animations (the gallery's and review_page.py's technique). Without the gate the
# fragment shows its resting frame (fragment contract, section 5): that is what reduced motion
# (the gate is never set; animations off as a backstop) and print (gate dropped on beforeprint,
# animations off, light colours on white paper) show.
DEMO_CSS = r"""
:root{
  --anim-theme-bg:#0F1E27;--anim-theme-panel:#0D1820;--anim-theme-line:#2A3D49;
  --anim-theme-fg:#E6EDF0;--anim-theme-muted:#93A7B2;--anim-theme-accent:#34D1BF;
  --anim-theme-accent-2:#FF8A3D;--anim-theme-ok:#8ED7AD;--anim-theme-warn:#FFD15C;
  --anim-theme-danger:#FF6B6B;color-scheme:dark;
}
@media (prefers-color-scheme: light){:root{
  --anim-theme-bg:#ffffff;--anim-theme-panel:#f2f4f8;--anim-theme-line:#c5ccd8;
  --anim-theme-fg:#14181f;--anim-theme-muted:#5b6474;--anim-theme-accent:#0a6cff;
  --anim-theme-accent-2:#d9480f;--anim-theme-ok:#2b8a3e;--anim-theme-warn:#e67700;
  --anim-theme-danger:#c92a2a;color-scheme:light}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--anim-theme-bg);color:var(--anim-theme-fg);
  font:16px/1.5 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}
main,footer{max-width:1280px;margin:0 auto;padding:0 16px}
main{padding-top:32px}
.kicker{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--anim-theme-muted);margin:0 0 6px}
h1{font-size:clamp(22px,3vw,32px);line-height:1.2;letter-spacing:-.01em;margin:0 0 6px}
.story{color:var(--anim-theme-muted);max-width:52em;margin:0 0 20px}
.scroll{overflow-x:auto;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch;--fl:0px;--fr:0px;
  -webkit-mask-image:linear-gradient(to right,transparent,#000 var(--fl),#000 calc(100% - var(--fr)),transparent);
  mask-image:linear-gradient(to right,transparent,#000 var(--fl),#000 calc(100% - var(--fr)),transparent)}
.scroll.fl{--fl:16px}.scroll.fr{--fr:16px}
.fit{width:100%;margin:0 auto}
.swipe{display:none;font-size:13px;color:var(--anim-theme-muted);margin:4px 0 0}
.bar{display:flex;align-items:center;gap:12px;margin:16px 0 24px}
.bar button{font:inherit;font-size:15px;font-weight:600;color:var(--anim-theme-fg);background:transparent;
  border:1px solid var(--anim-theme-line);border-radius:8px;padding:10px 20px;min-height:44px;cursor:pointer}
.bar button:hover,.bar button:focus-visible{border-color:var(--anim-theme-accent)}
footer{padding-top:14px;padding-bottom:32px;color:var(--anim-theme-muted);font-size:13px;
  border-top:1px solid var(--anim-theme-line)}
footer a{color:var(--anim-theme-accent)}
@media (max-width:760px){.scroll{margin:0 -16px}.scroll>.fit{min-width:740px}.swipe{display:block}}
@media (prefers-reduced-motion: reduce){.fit *{animation:none !important}.bar{display:none}}
@page{size:landscape;margin:12mm}
@media print{
  :root{--anim-theme-bg:#ffffff;--anim-theme-panel:#f2f4f8;--anim-theme-line:#c5ccd8;
    --anim-theme-fg:#14181f;--anim-theme-muted:#5b6474;--anim-theme-accent:#0a6cff;
    --anim-theme-accent-2:#d9480f;--anim-theme-ok:#2b8a3e;--anim-theme-warn:#e67700;
    --anim-theme-danger:#c92a2a;color-scheme:light}
  body{background:#fff}
  main,footer{max-width:none;padding-left:0;padding-right:0}
  .fit *{animation:none !important}
  .bar,.swipe{display:none !important}
  .scroll{overflow:visible;margin:0;-webkit-mask-image:none;mask-image:none}
  .scroll>.fit{min-width:0 !important}
}
"""

DEMO_JS = r"""
(function(){
  var f=document.getElementById('fig'),b=document.getElementById('replay');
  var rm=!!(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches);
  function anims(){return f.getAnimations?f.getAnimations({subtree:true}):[]}
  var s=f.parentNode;
  // a figure wider than the screen scrolls in its frame: open it centred on data-focus (a fraction
  // of the figure width) and fade only the clipped edges
  function fade(){var m=s.scrollWidth-s.clientWidth;s.classList.toggle('fl',m>1&&s.scrollLeft>1);
    s.classList.toggle('fr',m>1&&s.scrollLeft<m-1)}
  function focus(){var m=s.scrollWidth-s.clientWidth;if(m>1){var k=parseFloat(s.getAttribute('data-focus'));
    if(!(k>=0&&k<=1))k=.5;s.scrollLeft=Math.max(0,Math.min(m,k*s.scrollWidth-s.clientWidth/2))}fade()}
  function play(){f.classList.remove('visible');void f.offsetWidth;f.classList.add('visible');
    anims().forEach(function(a){try{a.currentTime=0;a.play()}catch(e){}});focus()}
  if(b)b.addEventListener('click',play);
  s.addEventListener('scroll',fade,{passive:true});window.addEventListener('resize',focus);focus();
  window.addEventListener('beforeprint',function(){f.classList.remove('visible')});
  window.addEventListener('afterprint',function(){if(rm)return;f.classList.add('visible');
    anims().forEach(function(a){try{a.finish()}catch(e){}})});
  if(!rm)play();
})();
"""


def demo_page(name, fragment_src, title=None, story='', repo_url=DEFAULT_REPO, focus=0.5):
    """A standalone, offline, playable HTML page around one fragment. The fragment source is
    embedded unchanged. focus: where a narrow screen's scroll frame opens, as a fraction (0..1)
    of the figure width. Returns the page as a string."""
    w, h = viewbox_of(fragment_src)
    focus = focus_of(focus, None, name)
    title = title or name
    repo = repo_url.rstrip('/') if repo_url else ''
    shown = re.sub(r'^https?://', '', repo)
    credit = (f'Made with anim-slides · <a href="{esc(repo)}">{esc(shown)}</a>' if repo
              else 'Made with anim-slides')
    story_p = f'<p class="story">{esc(story)}</p>' if story else ''
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark light">
<title>{esc(title)} · anim-slides</title>
<style>{DEMO_CSS}</style>
<noscript><style>.bar{{display:none}}</style></noscript>
</head>
<body>
<main>
<p class="kicker">anim-slides demo</p>
<h1>{esc(title)}</h1>
{story_p}
<div class="scroll" data-focus="{focus:g}"><div class="fit" id="fig" style="aspect-ratio:{w:g}/{h:g}">
{fragment_src}
</div></div>
<p class="swipe">Swipe sideways to see the whole figure.</p>
<div class="bar"><button type="button" id="replay">Replay</button></div>
</main>
<footer>{credit}</footer>
<script>{DEMO_JS}</script>
</body>
</html>
"""


def demo_main(argv):
    ap = argparse.ArgumentParser(prog='build_gallery.py --demo',
                                 description='Wrap one fragment in a standalone playable page.')
    ap.add_argument('--demo', required=True, metavar='FRAGMENT.html', help='fragment file to wrap')
    ap.add_argument('-o', '--out', required=True, metavar='OUT.html', help='page to write')
    ap.add_argument('--title', default=None, help='page heading (default: the fragment name)')
    ap.add_argument('--story', default='', help='one line under the heading')
    ap.add_argument('--focus', type=float, default=0.5,
                    help='where a narrow screen opens the figure, as a fraction 0..1 of its width (default 0.5)')
    ap.add_argument('--repo-url', default=DEFAULT_REPO, help=f'repository named in the footer (default {DEFAULT_REPO})')
    a = ap.parse_args(argv)
    if not os.path.isfile(a.demo):
        die(f'fragment not found: {a.demo}')
    src = open(a.demo, encoding='utf-8', newline='').read()
    m = re.search(r'\bdata-anim="([^"]+)"', src)
    name = m.group(1) if m else os.path.splitext(os.path.basename(a.demo))[0]
    out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(demo_page(name, src, a.title, a.story, a.repo_url, a.focus))
    print(f'build_gallery: demo for {name} -> {out}')


def main():
    if '--demo' in sys.argv[1:] or any(x.startswith('--demo=') for x in sys.argv[1:]):
        return demo_main(sys.argv[1:])
    ap = argparse.ArgumentParser(description='Build a static gallery site from an anim-slides pool.',
                                 epilog='Wrap one fragment instead: build_gallery.py --demo FRAGMENT.html -o OUT.html '
                                        '[--title TEXT] [--story TEXT] [--repo-url URL]')
    ap.add_argument('-o', '--out', required=True, help='output folder (created; existing files are replaced)')
    ap.add_argument('--pool', default=DEFAULT_POOL, help='pool folder with <name>/<name>.html and index.yaml '
                    '(default: the pool shipped with the skill)')
    ap.add_argument('--title', default=None, help='page title')
    ap.add_argument('--repo-url', default=None,
                    help='repository URL for source links and the install line '
                         '(default: https://github.com/KehanLiu/anim-slides for the shipped pool, none otherwise)')
    a = ap.parse_args()

    pool = os.path.abspath(a.pool)
    shipped = os.path.samefile(pool, DEFAULT_POOL) if os.path.isdir(DEFAULT_POOL) and os.path.isdir(pool) else False
    title = a.title or ('anim-slides pool' if shipped else f'{os.path.basename(pool)} pool')
    repo_url = a.repo_url if a.repo_url is not None else (DEFAULT_REPO if shipped else '')

    entries = load_pool(pool)
    out = os.path.abspath(a.out)
    if os.path.realpath(out) == os.path.realpath(pool):
        die('the output folder must not be the pool folder')
    os.makedirs(out, exist_ok=True)

    with open(os.path.join(out, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(build_index(entries, title, repo_url))
    for e in entries:
        d = os.path.join(out, e['name'])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(build_detail(e, title, repo_url))
        for fn in (f"{e['name']}.html", 'spec.yaml', 'thumb.png'):
            p = os.path.join(e['dir'], fn)
            if os.path.isfile(p):
                shutil.copyfile(p, os.path.join(d, fn))
        with open(os.path.join(d, f"{e['name']}-demo.html"), 'w', encoding='utf-8') as f:
            f.write(demo_page(e['name'], e['src'], e['name'], str(e.get('story') or ''), repo_url or DEFAULT_REPO,
                              e['focus']))
    open(os.path.join(out, '.nojekyll'), 'w').close()
    with open(os.path.join(out, 'pool.json'), 'w', encoding='utf-8') as f:
        json.dump([{k: e.get(k) for k in ('name', 'verb', 'archetype', 'domain', 'viewbox', 'control', 'cycle', 'story', 'tags')}
                   for e in entries], f, indent=1)
    print(f'build_gallery: {len(entries)} fragments -> {out}/index.html')


if __name__ == '__main__':
    main()
