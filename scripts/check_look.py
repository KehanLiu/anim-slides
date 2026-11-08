#!/usr/bin/env python3
"""Render-time look lint for an anim-slides fragment, or a slide of an integrated deck.

Usage:
  check_look.py FRAGMENT.html --rendered-width PX [--stage-width PX] [--slot W H] [--theme FILE]
  check_look.py --page DECK.html --slide N [--stage-width PX] [--window W H] [--keep-script]
  common: [--gate visible] [--bg COLOUR] [--json] [--chrome PATH] [--save-probe FILE]

check_fragment.py reads the source; this script measures the rendered result in headless Chrome
(no extra packages): a probe page inlines the fragment (or the deck with its slide N brought into
view), freezes every animation with the Web Animations API at the resting frame (gate removed)
and at each data-anim-phases mark (plus the pass end), and reads boxes, colours and sizes back
through --dump-dom. Checks (references/style.md principles and "Checklist before shipping"):
  clip      text or shape crossing the viewBox (or the --slot box)                 FAIL
  overlap   two visible labels overlapping > 2 px                                FAIL
            a label on a filled shape that is not a ground-coloured plate        WARN
  contrast  text vs ground (WCAG): labels < 3.0, text under 20 px (1920 stage) < 4.5,
            muted or dimmed text < 2.5                                           FAIL
            lines/strokes < 1.5                                                  WARN
  boxes     filled boxes (> 2 % of the viewBox) holding text: 1-3 WARN, > 3 FAIL;
            opt out with <!-- anim-look: boxes-ok --> when the box is the meaning
  colours   distinct hues (greys and the ground ignored): > 4 WARN, > 6 FAIL
  density   bbox union < 35 % or > 90 % of the viewBox, > 40 text elements       WARN
  text-size smallest rendered text below the check_fragment.py floor             FAIL
  fonts     a requested font family that is not available (fallback used)       WARN
  rest      resting frame differs from the last mark (opacity or position)      WARN
The ground is --anim-bg as the fragment resolves it (or --anim-theme-bg from --theme, or the
slide's own background in --page mode); --bg overrides it.
--page mode strips the deck's scripts (--keep-script keeps them) and measures every
.anim[data-anim] wrapper on slide N (Nth .slide, else Nth <section>); the stage width defaults
to the slide's width. Exit: 0 pass, 1 any FAIL, 2 bad input, 3 no Chrome found (set CHROME).
"""
import argparse, colorsys, json, math, os, re, shutil, subprocess, sys, tempfile

PROBE_JS = r"""
(function(){var CFG=__CFG__,OUT={frames:[]},cv=document.createElement('canvas');cv.width=cv.height=1;
var cx=cv.getContext('2d',{willReadFrequently:true}),cache={};
function col(s){if(!s||s==='none'||s.indexOf('url(')===0)return null;if(s in cache)return cache[s];
 cx.clearRect(0,0,1,1);cx.fillStyle='rgba(0,0,0,0)';cx.fillStyle=s;cx.fillRect(0,0,1,1);var d=cx.getImageData(0,0,1,1).data;
 return cache[s]=[d[0],d[1],d[2],+(d[3]/255).toFixed(3)];}
var GEN=/^(serif|sans-serif|monospace|cursive|fantasy|system-ui|ui-[a-z-]+|inherit|initial|emoji|math|fangsong|-apple-system|blinkmacsystemfont)$/i;
var fcache={};function hasFont(f){if(f in fcache)return fcache[f];var ok=false;
 document.fonts.forEach(function(ff){if(ff.family.replace(/["']/g,'').toLowerCase()===f.toLowerCase())ok=true;});
 var s='mmmmmmmmmmlli1WQ@#';['monospace','serif','sans-serif'].forEach(function(b){if(ok)return;cx.font='72px '+b;var w0=cx.measureText(s).width;
  cx.font='72px "'+f+'",'+b;if(cx.measureText(s).width!==w0)ok=true;});return fcache[f]=ok;}
try{var root,gate=CFG.gate;
 if(CFG.page){var l=document.querySelectorAll('.slide');if(!l.length)l=document.querySelectorAll('section');root=l[CFG.page-1];
  if(!root)throw new Error('no slide '+CFG.page+' ('+l.length+' slides found)');
  Array.prototype.forEach.call(l,function(x){if(x!==root)x.style.setProperty('display','none','important');});
  ['active','current','present'].forEach(function(c){root.classList.add(c);});
  if(getComputedStyle(root).display==='none')root.style.setProperty('display','block','important');
  window.scrollTo(0,0);root.scrollIntoView({block:'start',inline:'start'});OUT.stage=root.getBoundingClientRect().width;
 }else root=document.getElementById('probe');
 var W=Array.prototype.slice.call(root.querySelectorAll('.anim[data-anim],[data-anim]')).filter(function(w){return w.querySelector('svg');});
 if(!W.length)throw new Error('no .anim[data-anim] wrapper with an <svg>');
 var times=[];W.forEach(function(w){var c=parseFloat(w.getAttribute('data-anim-cycle'))||0;
  (w.getAttribute('data-anim-phases')||'').split(',').forEach(function(p){p=parseFloat(p);if(p>0)times.push(p);});if(c)times.push(c);});
 times=times.filter(function(t,i){return times.indexOf(t)===i;}).sort(function(a,b){return a-b;});
 function setFrame(t){var all=CFG.page?document.querySelectorAll('.'+gate):root.querySelectorAll('.'+gate);
  Array.prototype.forEach.call(all,function(x){x.classList.remove(gate);});root.classList.remove(gate);
  if(t!==null)root.classList.add(gate);
  document.getAnimations().forEach(function(a){var tg=a.effect&&a.effect.target,inF=tg&&W.some(function(w){return w.contains(tg);});
   if(inF&&t!==null){a.pause();a.currentTime=t*1000;}else{try{a.finish();}catch(e){a.cancel();}}});}
 function measure(w){var svg=w.querySelector('svg'),S=svg.getScreenCTM(),inv=S.inverse(),ss=Math.sqrt(Math.abs(S.a*S.d-S.b*S.c));
  var vb=svg.viewBox.baseVal,sr=svg.getBoundingClientRect(),cs0=getComputedStyle(w),tok={};
  ['bg','line','fg','muted','panel','font','mono'].forEach(function(k){tok[k]=cs0.getPropertyValue('--anim-'+k).trim();});
  function up(x,y){var p=new DOMPoint(x,y).matrixTransform(inv);return [p.x,p.y];}
  var a=up(sr.left,sr.top),b=up(sr.right,sr.bottom),els=[],nodes=[],texts=[],missing={};
  svg.querySelectorAll('text,rect,circle,ellipse,line,polyline,polygon,path,use').forEach(function(el){
   if(el.closest('defs,clipPath,mask,marker,pattern,symbol')||(el.tagName!=='text'&&el.closest('text')))return;
   var cs=getComputedStyle(el),op=1,disp=true;for(var x=el;x&&x!==w.parentNode;x=x.parentNode){var c=getComputedStyle(x);
    if(c.display==='none')disp=false;op*=parseFloat(c.opacity);}
   var r=clipr(el,el.getBoundingClientRect(),svg),p=up(r.left,r.top),q=up(r.right,r.bottom),M=el.getScreenCTM(),es=M?Math.sqrt(Math.abs(M.a*M.d-M.b*M.c)):ss;
   var e={i:nodes.length,tag:el.tagName,cls:(el.getAttribute('class')||'').slice(0,60),x:Math.min(p[0],q[0]),y:Math.min(p[1],q[1]),
    w:Math.abs(q[0]-p[0]),h:Math.abs(q[1]-p[1]),op:disp&&cs.visibility!=='hidden'?+op.toFixed(3):0,fill:col(cs.fill),stroke:col(cs.stroke),
    fo:+cs.fillOpacity,so:+cs.strokeOpacity,sw:(parseFloat(cs.strokeWidth)||0)*es/ss,glow:cs.filter!=='none',dash:cs.strokeDasharray!=='none'};
   if(r.out)e.op=0;
   if(e.tag==='text'){e.px=+(parseFloat(cs.fontSize)*es).toFixed(2);e.txt=el.textContent.trim().replace(/\s+/g,' ').slice(0,40);e.runs=[];
    Array.prototype.forEach.call(el.childNodes,function(n){var c=n.nodeType===3?cs:n.nodeType===1?getComputedStyle(n):null;
     if(c&&n.textContent.trim())e.runs.push([col(c.fill),+c.fillOpacity,n.nodeType===1?+c.opacity:1,n.textContent.trim().slice(0,30)]);});
    var f=cs.fontFamily.split(',')[0].trim().replace(/["']/g,'');e.font=f;if(e.op>0.05&&f&&!GEN.test(f)&&!hasFont(f))missing[f]=1;texts.push(e);}
   nodes.push(el);els.push(e);});
  var inside=[],boxlike=[];els.forEach(function(s,si){var el=nodes[si];
   if(s.tag==='text'||s.tag==='use'||!s.fill||s.op<=0.05||!el.isPointInFill)return;var M=el.getScreenCTM(),Mi;try{Mi=M.inverse();}catch(x){return;}
   function pin(x,y){var p=new DOMPoint(x,y).matrixTransform(S).matrixTransform(Mi);try{return el.isPointInFill(p);}catch(e){return false;}}
   var bl=s.tag==='rect';if(!bl&&(s.tag==='path'||s.tag==='polygon')){bl=true;[[.5,.5],[.12,.12],[.88,.12],[.12,.88],[.88,.88]].forEach(function(f){
    if(!pin(s.x+f[0]*s.w,s.y+f[1]*s.h))bl=false;});}if(bl)boxlike.push(si);
   texts.forEach(function(t){if(t.op>0.05&&pin(t.x+t.w/2,t.y+t.h/2))inside.push([t.i,si]);});});
  return {name:w.getAttribute('data-anim'),vb:[vb.x,vb.y,vb.width,vb.height],view:[a[0],a[1],b[0]-a[0],b[1]-a[1]],scale:ss,
   control:w.getAttribute('data-anim-control')||'once',tok:tok,tokc:{bg:col(tok.bg),line:col(tok.line),fg:col(tok.fg),muted:col(tok.muted),panel:col(tok.panel)},
   els:els,inside:inside,boxlike:boxlike,missing:Object.keys(missing),boxesok:/anim-look:\s*boxes-ok/.test((w.parentNode||w).innerHTML)};}
 function clipr(el,r,svg){var L=r.left,T=r.top,R=r.right,B=r.bottom;for(var x=el;x&&x!==svg;x=x.parentNode){var cs=getComputedStyle(x);
   [cs.clipPath,cs.maskImage||cs.webkitMaskImage].forEach(function(v){var m=/url\(["']?#([^"')]+)/.exec(v||'');if(!m)return;var cp=document.getElementById(m[1]);
    if(!cp||!x.getScreenCTM)return;var M=x.getScreenCTM(),u=null;Array.prototype.forEach.call(cp.children,function(c){if(!c.getBBox)return;var b=c.getBBox();
     u=u?{x0:Math.min(u.x0,b.x),y0:Math.min(u.y0,b.y),x1:Math.max(u.x1,b.x+b.width),y1:Math.max(u.y1,b.y+b.height)}:{x0:b.x,y0:b.y,x1:b.x+b.width,y1:b.y+b.height};});
    if(!u||cp.getAttribute('clipPathUnits')==='objectBoundingBox'||cp.getAttribute('maskContentUnits')==='objectBoundingBox')return;
    var P=[[u.x0,u.y0],[u.x1,u.y0],[u.x0,u.y1],[u.x1,u.y1]].map(function(q){return new DOMPoint(q[0],q[1]).matrixTransform(M);});
    L=Math.max(L,Math.min.apply(0,P.map(function(q){return q.x;})));R=Math.min(R,Math.max.apply(0,P.map(function(q){return q.x;})));
    T=Math.max(T,Math.min.apply(0,P.map(function(q){return q.y;})));B=Math.min(B,Math.max.apply(0,P.map(function(q){return q.y;})));});}
  return {left:L,top:T,right:Math.max(L,R),bottom:Math.max(T,B),out:R<L-0.5||B<T-0.5};}
 function ground(w){var cs=[];for(var x=w;x&&x.nodeType===1;x=x.parentNode)cs.push(col(getComputedStyle(x).backgroundColor));
  var g=[255,255,255];for(var i=cs.length-1;i>=0;i--){var c=cs[i];if(c&&c[3]>0)g=[0,1,2].map(function(k){return c[k]*c[3]+g[k]*(1-c[3]);});}return g;}
 [null].concat(times).forEach(function(t){setFrame(t);OUT.frames.push({t:t===null?'rest':t,frags:W.map(measure)});});
 setFrame(null);OUT.ground=W.map(function(w){return CFG.page?ground(w):col(getComputedStyle(w).getPropertyValue('--anim-bg').trim())||ground(w);});
}catch(e){OUT.error=String(e&&e.stack||e);}
document.getElementById('look').textContent=JSON.stringify(OUT).replace(/</g,'\\u003c');})();
"""


def find_chrome(explicit=None):
    for c in [explicit, os.environ.get('CHROME'),
              '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
              '/Applications/Chromium.app/Contents/MacOS/Chromium',
              '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
              os.path.expanduser('~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')]:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
        if c and shutil.which(c):
            return shutil.which(c)
    for c in ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'microsoft-edge']:
        if shutil.which(c):
            return shutil.which(c)
    return None


def run_probe(chrome, html, base_dir, win):
    fd, path = tempfile.mkstemp(suffix='.html', prefix='check-look-')  # <base href> resolves assets
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(html)
        cmd = [chrome, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
               '--window-size=%d,%d' % win, '--dump-dom', 'file://' + os.path.abspath(path)]
        if os.environ.get('CI') or (hasattr(os, 'geteuid') and os.geteuid() == 0):
            cmd.insert(1, '--no-sandbox')
        dom = subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout
    finally:
        os.unlink(path)
    m = re.search(r'<script type="application/json" id="look">(.*?)</script>', dom, re.S)
    if not m or not m.group(1).strip():
        raise RuntimeError('Chrome returned no measurement (probe did not run)')
    data = json.loads(m.group(1))
    if data.get('error'):
        raise RuntimeError('probe error: ' + data['error'].split('\n')[0])
    return data


# ---------------------------------------------------------------------------- colour maths
def lum(c):
    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def over(c, alpha, g):
    return [c[k] * alpha + g[k] * (1 - alpha) for k in range(3)]


def dist(a, b):
    return math.sqrt(sum((a[k] - b[k]) ** 2 for k in range(3)))


def hexc(c):
    return '#%02X%02X%02X' % tuple(int(round(v)) for v in c[:3])


def label(e):
    if e.get('txt'):
        return '"%s"' % e['txt']
    return '<%s class="%s">' % (e['tag'], e['cls']) if e['cls'] else '<%s> at %.0f,%.0f' % (e['tag'], e['x'], e['y'])


def few(items, n=3):
    return ', '.join(items[:n]) + (' and %d more' % (len(items) - n) if len(items) > n else '')


# ---------------------------------------------------------------------------- analysis
def analyse(frames, k, gcol, a, R, pre):
    rest = frames[0]['frags'][k]
    F = [(fr['t'], fr['frags'][k]) for fr in frames]
    vbx, vby, vbw, vbh = rest['vb']
    clip = rest['view'] if a.slot or a.page else rest['vb']
    g = gcol[:3]
    tok = rest['tokc']
    floor = a.min_text
    R.info(pre + 'frames', 'measured rest + %s; ground %s; %d elements' % (
        ', '.join('%gs' % t for t, _ in F[1:]) or 'no marks', hexc(g), len(rest['els'])))

    def vis(e):
        return e['op'] > 0.05 and (e['w'] > 0 or e['h'] > 0)

    # 1 clipping, 2 overlap: every frame
    clipped, overl = {}, {}
    for t, fr in F:
        cx0, cy0, cw, ch = clip
        for e in fr['els']:
            if not vis(e) or e['glow']:
                continue
            pad = e['sw'] / 2 if e['tag'] != 'text' and e['stroke'] and e['stroke'][3] > 0 else 0
            ox = max(cx0 - (e['x'] - pad), (e['x'] + e['w'] + pad) - (cx0 + cw), 0)
            oy = max(cy0 - (e['y'] - pad), (e['y'] + e['h'] + pad) - (cy0 + ch), 0)
            if e['tag'] != 'text':  # a band, ground or line running along the edge is deliberate bleed
                ox = 0 if e['h'] >= 0.25 * ch else ox
                oy = 0 if e['w'] >= 0.25 * cw else oy
            lim = 1 if e['tag'] == 'text' else 2
            if (ox > lim or oy > lim) and e['i'] not in clipped:
                clipped[e['i']] = '%s %s by %.0f units at %s' % (label(e), 'sticks out', max(ox, oy), t if t == 'rest' else '%gs' % t)
        T = [e for e in fr['els'] if e['tag'] == 'text' and vis(e)]
        for i in range(len(T)):
            for j in range(i + 1, len(T)):
                p, q = T[i], T[j]
                ip, iq = 0.15 * p['h'], 0.15 * q['h']  # glyph boxes carry ascender/descender air
                ix = min(p['x'] + p['w'], q['x'] + q['w']) - max(p['x'], q['x'])
                iy = min(p['y'] + p['h'] - ip, q['y'] + q['h'] - iq) - max(p['y'] + ip, q['y'] + iq)
                key = (p['i'], q['i'])
                if p['txt'] == q['txt'] and max(abs(p['x'] - q['x']), abs(p['y'] - q['y']), abs(p['w'] - q['w'])) < 3:
                    continue  # a highlight twin drawn over its base label reads as one label
                if ix > 2 and iy > 2 and key not in overl:
                    overl[key] = '%s and %s overlap by %.0fx%.0f at %s' % (label(p), label(q), ix, iy, t if t == 'rest' else '%gs' % t)
    for m in clipped.values():
        R.fail(pre + 'clip', m + ': move it inside the viewBox, shorten the label or widen the viewBox')
    for m in overl.values():
        R.fail(pre + 'overlap', m + ': move one, stack them with more gap, or drop one')

    els = rest['els']
    T = [e for e in els if e['tag'] == 'text' and vis(e)]
    filled = {}
    for e in els:
        if e['tag'] != 'text' and e['fill'] and vis(e) and not e['glow']:
            al = e['fill'][3] * e['fo'] * e['op']
            comp = over(e['fill'], al, g)
            if al > 0.08 and dist(comp, g) >= 6:  # a ground-coloured fill is a label plate
                filled[e['i']] = e
    on_shape = sorted({ti for ti, si in rest['inside'] if si in filled and els[ti]['tag'] == 'text'})
    if on_shape:
        R.warn(pre + 'overlap', '%d label(s) sit on a filled shape: %s; put labels on the ground or on a plate in --anim-bg'
               % (len(on_shape), few([label(els[i]) for i in on_shape])))

    # 3 contrast (rest)
    bad = []
    def twin_over(e):  # a brighter copy drawn at the same place covers a dimmed base label
        return any(q is not e and q['txt'] == e['txt'] and q['op'] > e['op'] + 0.05 and
                   abs(q['x'] - e['x']) < 3 and abs(q['y'] - e['y']) < 3 for q in T)
    for e in T:
        if twin_over(e):
            continue
        worst = None
        for fill, fo, om, txt in e.get('runs') or []:
            op = e['op'] * om
            if not fill or op <= 0.05:
                continue
            c = ratio(over(fill, fill[3] * fo * op, g), g)
            px1920 = e['px'] * 1920.0 / a.stage_width
            muted = bool(tok.get('muted') and dist(fill, tok['muted']) < 10) or op < 0.6
            need = 2.5 if muted else 4.5 if px1920 < 20 else 3.0
            if c < need and (worst is None or c < worst[0]):
                worst = (c, '"%s" %.2f:1 < %.1f (%s %s%s)' % (txt, math.floor(c * 100) / 100, need, hexc(fill), 'muted' if muted else
                         '%.0fpx' % px1920, ', opacity %.2f' % op if op < 0.99 else ''))
        if worst:
            bad.append(worst)
    for c, m in sorted(bad)[:6]:
        R.fail(pre + 'contrast', m + ' on ground %s: use --anim-fg/--anim-muted, raise the opacity' % hexc(g))
    if len(bad) > 6:
        R.fail(pre + 'contrast', '%d more labels below their contrast floor' % (len(bad) - 6))
    faint = []
    for e in els:
        if vis(e) and e['tag'] != 'text' and not e['glow'] and e['stroke'] and e['sw'] > 0 and dist(e['stroke'], g) >= 6:
            al = e['stroke'][3] * e['so'] * e['op']
            if al > 0.02:
                c = ratio(over(e['stroke'], al, g), g)
                if c < 1.5 and not (e['dash'] and c >= 1.1):  # dotted gridlines may be fainter (style.md chart)
                    faint.append((c, e))
    if faint:
        faint.sort(key=lambda x: x[0])
        R.warn(pre + 'contrast', 'faint lines on this ground: %d stroke(s) below 1.5:1, faintest %.2f:1 (%s %s); darken '
               '--anim-line for this ground or raise faded opacities' % (len(faint), faint[0][0], label(faint[0][1]), hexc(faint[0][1]['stroke'])))

    # 4 boxes
    vba = vbw * vbh
    boxes = sorted({si for ti, si in rest['inside'] if si in filled and si in rest['boxlike']
                    and filled[si]['w'] * filled[si]['h'] >= 0.02 * vba})
    if boxes:
        msg = '%d filled box(es) holding text: %s' % (len(boxes), few([label(els[i]) for i in boxes]))
        if rest['boxesok']:
            R.info(pre + 'boxes', msg + ' (anim-look: boxes-ok)')
        elif len(boxes) > 3:
            R.fail(pre + 'boxes', msg + '; style.md principle 2: labels on the ground, rings, hairline brackets '
                   '(add <!-- anim-look: boxes-ok --> only when the box is the meaning)')
        else:
            R.warn(pre + 'boxes', msg + '; keep only boxes that are the meaning (style.md principle 2)')

    # 5 colours
    neutral = [c for c in (tok.get(n) for n in ('bg', 'line', 'fg', 'muted', 'panel')) if c] + [g]
    hues = []
    for e in els:
        if not vis(e) or e['glow']:
            continue
        for c, o in ((e['fill'], e['fo']), (e['stroke'], e['so'] if e['sw'] > 0 else 0)):
            if not c or c[3] * o * e['op'] <= 0.05 or any(dist(c, n) < 20 for n in neutral):
                continue
            comp = over(c, c[3] * o * e['op'], g)
            if max(comp) - min(comp) >= 40:
                hues.append(colorsys.rgb_to_hls(*[v / 255.0 for v in c[:3]])[0] * 360)
    hues.sort()
    clusters = []
    for h in hues:
        if clusters and h - clusters[-1][-1] < 18:
            clusters[-1].append(h)
        else:
            clusters.append([h])
    if len(clusters) > 1 and clusters[0][0] + 360 - clusters[-1][-1] < 18:
        clusters[0] = clusters.pop() + clusters[0]
    n = len(clusters)
    hl = ', '.join('%.0f' % (sum(c) / len(c) % 360) for c in clusters)
    if n > 6:
        R.fail(pre + 'colours', '%d distinct hues (%s deg): one accent plus at most two semantic colours (style.md principle 3)' % (n, hl))
    elif n > 4:
        R.warn(pre + 'colours', '%d distinct hues (%s deg): one accent plus at most two semantic colours' % (n, hl))
    else:
        R.info(pre + 'colours', '%d hue(s)%s' % (n, ' (%s deg)' % hl if n else ''))

    # 6 density
    GX, GY = 160, 90
    grid = set()
    for e in els:
        if not vis(e):
            continue
        x0 = int(max(0, (e['x'] - vbx) / vbw * GX)); x1 = int(min(GX, math.ceil((e['x'] + e['w'] - vbx) / vbw * GX)))
        y0 = int(max(0, (e['y'] - vby) / vbh * GY)); y1 = int(min(GY, math.ceil((e['y'] + e['h'] - vby) / vbh * GY)))
        grid.update((i, j) for i in range(x0, max(x1, x0 + 1)) for j in range(y0, max(y1, y0 + 1)) if i < GX and j < GY)
    cov = 100.0 * len(grid) / (GX * GY)
    ext = 100.0 * ((max(i for i, j in grid) - min(i for i, j in grid) + 1) * (max(j for i, j in grid) - min(j for i, j in grid) + 1)
                   / (GX * GY)) if grid else 0
    if ext < 35:
        R.warn(pre + 'density', 'mostly empty: the figure spans %.0f %% of the viewBox; crop the viewBox to the figure' % ext)
    elif cov > 90:
        R.warn(pre + 'density', 'no breathing room: element boxes cover %.0f %% of the viewBox; remove elements or add margin' % cov)
    else:
        R.info(pre + 'density', 'figure spans %.0f %% of the viewBox, element boxes cover %.0f %%' % (ext, cov))
    if len(T) > 40:
        R.warn(pre + 'density', '%d visible text elements at rest: drop labels before shrinking type' % len(T))

    # 7 smallest rendered text
    small = sorted((e['px'], label(e)) for e in T)
    under = [s for s in small if s[0] < floor - 0.05]
    for px, lb in under[:5]:
        R.fail(pre + 'text-size', '%s renders at %.1fpx < floor %gpx: raise its font-size in viewBox units' % (lb, px, floor))
    if small and not under:
        R.info(pre + 'text-size', 'smallest text %.1fpx at %.0fpx wide (floor %g)' % (small[0][0], vbw * rest['scale'], floor))

    # 8 fonts
    for f in rest['missing']:
        R.warn(pre + 'fonts', 'font "%s" is not available here, a fallback renders instead: install or embed it, '
               'or put a fallback with similar metrics after it' % f)

    # 9 resting frame vs last mark
    if rest['control'] != 'loop' and len(F) > 1:
        last_t, last = F[-1]
        diff = []
        for e, f in zip(els, last['els']):
            if abs(e['op'] - f['op']) > 0.1 and max(e['op'], f['op']) > 0.05:
                diff.append('%s opacity %.2f at rest vs %.2f' % (label(e), e['op'], f['op']))
            elif vis(e) and vis(f) and max(abs(e['x'] - f['x']), abs(e['y'] - f['y'])) > 2:
                diff.append('%s moved %.0f units' % (label(e), max(abs(e['x'] - f['x']), abs(e['y'] - f['y']))))
        if diff:
            R.warn(pre + 'rest', 'rest differs from last mark (%gs) in %d element(s): %s; the 100 %% keyframe must equal '
                   'the resting frame' % (last_t, len(diff), few(diff)))


class Report:
    def __init__(self):
        self.items = []

    def add(self, lvl, chk, msg):
        if (lvl, chk, msg) not in self.items:
            self.items.append((lvl, chk, msg))

    def info(self, c, m): self.add('INFO', c, m)
    def warn(self, c, m): self.add('WARN', c, m)
    def fail(self, c, m): self.add('FAIL', c, m)

    def count(self, lvl):
        return sum(1 for i in self.items if i[0] == lvl)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('fragment', nargs='?')
    ap.add_argument('--rendered-width', type=float, metavar='PX', help='fragment mode: width the SVG is shown at')
    ap.add_argument('--stage-width', type=float, metavar='PX', help='host stage width (text floor; page mode: slide width)')
    ap.add_argument('--min-text', type=float, metavar='PX', help='explicit text floor, overrides --stage-width')
    ap.add_argument('--slot', type=float, nargs=2, metavar=('W', 'H'), help='fragment mode: the slot box in CSS px')
    ap.add_argument('--theme', metavar='FILE', help='host theme CSS (host_theme.py output)')
    ap.add_argument('--page', metavar='DECK', help='measure a slide of an integrated deck')
    ap.add_argument('--slide', type=int, default=1, metavar='N')
    ap.add_argument('--window', type=int, nargs=2, default=[1920, 1080], metavar=('W', 'H'))
    ap.add_argument('--keep-script', action='store_true', help='page mode: keep the deck scripts')
    ap.add_argument('--gate', default='visible', help='gate class (default visible)')
    ap.add_argument('--bg', help='ground colour override, e.g. #FFFFFF')
    ap.add_argument('--chrome', help='Chrome binary (else $CHROME or auto-detected)')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--save-probe', metavar='FILE', help='also write the probe page (ends on the resting frame) to FILE')
    a = ap.parse_args()
    if bool(a.page) == bool(a.fragment):
        ap.error('give FRAGMENT or --page DECK')
    if a.fragment and not (a.rendered_width or a.slot):
        ap.error('fragment mode needs --rendered-width (or --slot)')
    chrome = find_chrome(a.chrome)
    if not chrome:
        print('SKIP: no Chrome/Chromium/Edge found; set CHROME=/path/to/chrome', file=sys.stderr)
        sys.exit(3)
    theme = ''
    if a.theme:
        theme = '<style>%s</style>' % open(a.theme, encoding='utf-8').read()
    cfg = {'gate': a.gate, 'page': a.slide if a.page else 0}
    js = '<script type="application/json" id="look"></script><script>%s</script>' % PROBE_JS.replace('__CFG__', json.dumps(cfg))
    notrans = '<style>*,*::before,*::after{transition:none!important}</style>'
    src_path = a.page or a.fragment
    try:
        src = open(src_path, encoding='utf-8', errors='replace').read()
    except OSError as e:
        print('error: %s' % e, file=sys.stderr); sys.exit(2)
    base_dir = os.path.dirname(os.path.abspath(src_path))
    base = '<base href="file://%s/">' % base_dir
    if a.page:
        if not a.keep_script:
            src = re.sub(r'<script\b[^>]*>.*?</script\s*>', '', src, flags=re.I | re.S)
        head = base + theme + notrans
        m = re.search(r'<head\b[^>]*>', src, re.I)
        src = src[:m.end()] + head + src[m.end():] if m else head + src
        ends = list(re.finditer(r'</body\s*>', src, re.I))
        html = src[:ends[-1].start()] + js + src[ends[-1].start():] if ends else src + js
        win = tuple(a.window)
    else:
        vb = re.search(r'<svg\b[^>]*\bviewBox="\s*([-\d.]+)[\s,]+([-\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)', src)
        if not vb:
            print('error: no viewBox on the <svg>', file=sys.stderr); sys.exit(2)
        vbw, vbh = float(vb.group(3)), float(vb.group(4))
        W, H = a.slot if a.slot else (a.rendered_width, a.rendered_width * vbh / vbw)
        pagebg = ('var(--anim-theme-bg,%s)' % (a.bg or '#0F1E27')) if a.theme else (a.bg or '#0F1E27')
        html = ('<!doctype html><meta charset=utf-8>%s%s%s<style>html,body{margin:0;background:%s}#probe{width:%.2fpx;height:%.2fpx}'
                '</style><section id="probe" class="%s">%s</section>%s' % (base, theme, notrans, pagebg, W, H,
                                                                           'anim-lean' if a.theme else '', src, js))
        win = (int(math.ceil(W)), int(math.ceil(H)))
    if a.save_probe:
        open(a.save_probe, 'w', encoding='utf-8').write(html)
    try:
        data = run_probe(chrome, html, base_dir, win)
    except (RuntimeError, subprocess.TimeoutExpired, ValueError) as e:
        print('error: %s' % e, file=sys.stderr); sys.exit(2)
    if a.stage_width is None:
        a.stage_width = data.get('stage') if a.page and data.get('stage') else 1920.0
    if a.min_text is None:
        a.min_text = round(max(10.0, 18 * a.stage_width / 1920), 2)
    R = Report()
    frames = data['frames']
    nfr = len(frames[0]['frags'])
    for k in range(nfr):
        name = frames[0]['frags'][k]['name']
        pre = (name + ' ') if nfr > 1 or a.page else ''
        gcol = data['ground'][k]
        if a.bg:
            gcol = [int(a.bg.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
        if a.fragment and re.search(r'anim-look:\s*boxes-ok', src):
            frames[0]['frags'][k]['boxesok'] = True
        analyse(frames, k, gcol, a, R, pre)
    nf, nw = R.count('FAIL'), R.count('WARN')
    if a.json:
        print(json.dumps({'source': src_path, 'slide': a.slide if a.page else None, 'fail': nf, 'warn': nw,
                          'items': [{'level': l, 'check': c, 'msg': m} for l, c, m in R.items]}, indent=1))
    else:
        for l, c, m in R.items:
            print('%-4s %s: %s' % (l, c, m))
        print('%s: %d fail, %d warn' % ('PASS' if nf == 0 else 'FAILED', nf, nw))
    sys.exit(1 if nf else 0)


if __name__ == '__main__':
    main()
