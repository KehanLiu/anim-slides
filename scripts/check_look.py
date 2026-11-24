#!/usr/bin/env python3
"""Render-time look lint for an anim-slides fragment, or a slide of an integrated deck.

Usage:
  check_look.py FRAGMENT.html --rendered-width PX [--stage-width PX] [--slot W H] [--theme FILE]
  check_look.py --page DECK.html --slide N [--stage-width PX] [--window W H] [--keep-script] [--min-gap PX]
  common: [--at-marks] [--at-pauses [N]] [--gate visible] [--bg COLOUR] [--json] [--chrome PATH] [--save-probe FILE]

check_fragment.py reads the source; this script measures the rendered result in headless Chrome
(no extra packages): a probe page inlines the fragment (or the deck with its slide N brought into
view), freezes every animation with the Web Animations API at the resting frame (gate removed)
and at each data-anim-phases mark (plus the pass end), and reads boxes, colours and sizes back
through --dump-dom. Checks (references/style.md principles and "Checklist before shipping"):
  clip      text or shape crossing the viewBox (or the --slot box)                 FAIL
            (clip-path: url(#...) clips by its shapes' boxes; inset(), polygon() and the
            other basic shapes by the browser's hit test of the element at that frame, so
            a part clipped away there is not visible to clip, overlap and contrast)
  overlap   two visible labels overlapping > 2 px                                FAIL
            a label on a filled shape that is not a ground-coloured plate        WARN
  contrast  text vs ground (WCAG): labels < 3.0, text under 20 px (1920 stage) < 4.5,
            muted or dimmed text < 2.5                                           FAIL
            faded or dashed lines/strokes < 1.5                                   WARN
  line-contrast  a solid structure stroke (opacity > 0.5, not scene) < 3.0        WARN
  accent-area    accent (and its glow) above 25 % of the ink at rest, measured from
            the pixels of one screenshot of the resting frame (data-anim-scene ground
            hidden; ground, accent by its blend weight from the ground, other ink);
            without a screenshot estimated from element geometry, above 25 %     WARN
  focal     data-anim-focal not visible at rest, focal text < 1.5x the median
            text size, or a focal shape that is smaller than the median shape box
            and has neither the heaviest (or 1.5x median) stroke, the only glow
            nor hero text                                                         WARN
  boxes     filled boxes (> 2 % of the viewBox) holding text: 1-3 WARN, > 3 FAIL;
            opt out with <!-- anim-look: boxes-ok --> when the box is the meaning
  scene     shapes carrying data-anim-scene (or inside a <g data-anim-scene>) are scene
            ground, the thing itself drawn (water, land, a chamber wall): exempt from
            boxes and the label-on-fill warning, everything else checked as before;
            more than half the filled shapes marked scene in a figure with 3+
            labelled rings (a node diagram)                                     WARN
  colours   distinct hues (greys and the ground ignored): > 4 WARN, > 6 FAIL
  density   bbox union < 35 % or > 90 % of the viewBox, > 40 text elements,
            drawn extent < 60 % of the slot (or viewBox) both ways               WARN
  text-size smallest rendered text below the check_fragment.py floor             FAIL
  fonts     a requested font family that is not available (fallback used), unless
            the stack names system-ui or ui-monospace as its fallback          WARN
  rest      resting frame differs from the last mark (opacity or position)      WARN
  gap       --page: fragment ink covering the slide's own text or pictures      FAIL
            nearer to them than --min-gap (default 24 px at a 1920 window)       WARN
Clip and overlap run on every frame. Contrast, text-size and gap run on the resting frame;
--at-marks runs them on every phase mark too (a label shown at a mark must be readable there,
not only at rest) and prints one INFO line per mark:
  INFO marks: at 2s: clip 0, overlap 0, contrast 0, text-size 0, gap 31px
--at-pauses [N] (default 3) freezes each fragment at N reproducible times strictly between 0.5 s and
its last phase mark (seeded from its data-anim name; >= 0.4 s apart, >= 0.15 s from any mark) and runs
clip, overlap and text-size there, tolerant of mid-motion: elements under opacity 0.15 are skipped and
two labels only overlap when both are at 0.6 or more (a cross-fade). Findings are WARN "[pause] at Ns",
never FAIL. Orphan labels (a label shown before its shape) are left to the reviewer's eye.
The ground is --anim-bg as the fragment resolves it (or --anim-theme-bg from --theme, or the
slide's own background in --page mode); --bg overrides it.
--page mode strips the deck's scripts (--keep-script keeps them) and measures every
.anim[data-anim] wrapper on slide N (Nth .slide, else Nth <section>); the stage width defaults
to the slide's width. Exit: 0 pass, 1 any FAIL, 2 bad input, 3 no Chrome found (set CHROME).
"""
import argparse, colorsys, json, math, os, re, shutil, struct, subprocess, sys, tempfile, zlib

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
try{var root,gate=CFG.gate,pe=document.createElement('style');
 pe.textContent='svg[data-look-pe],svg[data-look-pe] *{pointer-events:none!important}';document.head.appendChild(pe);
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
  ['bg','line','fg','muted','panel','accent','accent-2','ok','warn','danger','font','mono'].forEach(function(k){tok[k]=cs0.getPropertyValue('--anim-'+k).trim();});
  function up(x,y){var p=new DOMPoint(x,y).matrixTransform(inv);return [p.x,p.y];}
  var a=up(sr.left,sr.top),b=up(sr.right,sr.bottom),els=[],nodes=[],texts=[],missing={};
  svg.querySelectorAll('text,rect,circle,ellipse,line,polyline,polygon,path,use').forEach(function(el){
   if(el.closest('defs,clipPath,mask,marker,pattern,symbol')||(el.tagName!=='text'&&el.closest('text')))return;
   var cs=getComputedStyle(el),op=1,disp=true;for(var x=el;x&&x!==w.parentNode;x=x.parentNode){var c=getComputedStyle(x);
    if(c.display==='none')disp=false;op*=parseFloat(c.opacity);}
   var r=clipr(el,el.getBoundingClientRect(),svg),p=up(r.left,r.top),q=up(r.right,r.bottom),M=el.getScreenCTM(),es=M?Math.sqrt(Math.abs(M.a*M.d-M.b*M.c)):ss;
   var e={i:nodes.length,tag:el.tagName,cls:(el.getAttribute('class')||'').slice(0,60),x:Math.min(p[0],q[0]),y:Math.min(p[1],q[1]),
    w:Math.abs(q[0]-p[0]),h:Math.abs(q[1]-p[1]),op:disp&&cs.visibility!=='hidden'?+op.toFixed(3):0,fill:col(cs.fill),stroke:col(cs.stroke),
    fo:+cs.fillOpacity,so:+cs.strokeOpacity,sw:(parseFloat(cs.strokeWidth)||0)*es/ss,glow:cs.filter!=='none',dash:cs.strokeDasharray!=='none',scene:!!el.closest('[data-anim-scene]'),focal:!!el.closest('[data-anim-focal]')};
   if(el.getTotalLength&&e.tag!=='text'&&e.tag!=='use'){try{e.len=el.getTotalLength()*es/ss;}catch(x){}}
   if(r.out)e.op=0;
   if(e.tag==='text'){e.px=+(parseFloat(cs.fontSize)*es).toFixed(2);e.txt=el.textContent.trim().replace(/\s+/g,' ').slice(0,40);e.runs=[];
    Array.prototype.forEach.call(el.childNodes,function(n){var c=n.nodeType===3?cs:n.nodeType===1?getComputedStyle(n):null;
     if(c&&n.textContent.trim())e.runs.push([col(c.fill),+c.fillOpacity,n.nodeType===1?+c.opacity:1,n.textContent.trim().slice(0,30)]);});
    var f=cs.fontFamily.split(',')[0].trim().replace(/["']/g,'');e.font=f;if(e.op>0.05&&f&&!GEN.test(f)&&!hasFont(f)&&!/(^|,)\s*(system-ui|ui-sans-serif|ui-serif|ui-monospace|-apple-system)\s*(,|$)/.test(cs.fontFamily))missing[f]=1;texts.push(e);}
   nodes.push(el);els.push(e);});
  var inside=[],boxlike=[];els.forEach(function(s,si){var el=nodes[si];
   if(s.tag==='text'||s.tag==='use'||!s.fill||s.op<=0.05||!el.isPointInFill)return;var M=el.getScreenCTM(),Mi;try{Mi=M.inverse();}catch(x){return;}
   function pin(x,y){var p=new DOMPoint(x,y).matrixTransform(S).matrixTransform(Mi);try{return el.isPointInFill(p);}catch(e){return false;}}
   var bl=s.tag==='rect';if(!bl&&(s.tag==='path'||s.tag==='polygon')){bl=true;[[.5,.5],[.12,.12],[.88,.12],[.12,.88],[.88,.88]].forEach(function(f){
    if(!pin(s.x+f[0]*s.w,s.y+f[1]*s.h))bl=false;});}if(bl)boxlike.push(si);
   texts.forEach(function(t){if(t.op>0.05&&pin(t.x+t.w/2,t.y+t.h/2))inside.push([t.i,si]);});});
  return {name:w.getAttribute('data-anim'),vb:[vb.x,vb.y,vb.width,vb.height],view:[a[0],a[1],b[0]-a[0],b[1]-a[1]],scale:ss,ctm:[S.a,S.b,S.c,S.d,S.e,S.f],
   control:w.getAttribute('data-anim-control')||'once',tok:tok,tokc:{bg:col(tok.bg),line:col(tok.line),fg:col(tok.fg),muted:col(tok.muted),panel:col(tok.panel),accent:col(tok.accent),
    'accent-2':col(tok['accent-2']),ok:col(tok.ok),warn:col(tok.warn),danger:col(tok.danger)},
   els:els,inside:inside,boxlike:boxlike,missing:Object.keys(missing),boxesok:/anim-look:\s*boxes-ok/.test((w.parentNode||w).innerHTML)};}
 function neighbours(){var nb=[];if(!CFG.page)return nb;   // the slide's own text and pictures, in screen px
  function mine(e){return W.some(function(w){return w.contains(e);});}
  function shown(e){var op=1;for(var x=e;x&&x.nodeType===1;x=x.parentNode){var c=getComputedStyle(x);
   if(c.display==='none'||c.visibility==='hidden')return 0;op*=parseFloat(c.opacity);}return op;}
  function add(r,e,txt){if(r.width<1||r.height<1)return;var op=shown(e);if(op<=0.05)return;
   nb.push({x:r.left,y:r.top,w:r.width,h:r.height,txt:txt,op:+op.toFixed(2)});}
  var tw=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,null),tn;
  while((tn=tw.nextNode())){var p=tn.parentElement;if(!tn.nodeValue.trim()||!p||mine(p)||p.closest('script,style,template,aside.notes,.notes,svg'))continue;
   var rg=document.createRange();rg.selectNodeContents(tn);var t=tn.nodeValue.trim().replace(/\s+/g,' ').slice(0,30);
   Array.prototype.forEach.call(rg.getClientRects(),function(r){add(r,p,t);});}
  root.querySelectorAll('img,svg,video,canvas,iframe,object,embed').forEach(function(e){
   if(mine(e)||(e.tagName.toLowerCase()==='svg'&&e.parentElement&&e.parentElement.closest('svg')))return;
   add(e.getBoundingClientRect(),e,'<'+e.tagName.toLowerCase()+(e.id?'#'+e.id:'')+'>');});
  return nb;}
 function hitbox(el,L,T,R,B){var sv=el.ownerSVGElement;if(!sv)return null;sv.setAttribute('data-look-pe','');
   var pv=el.style.getPropertyValue('pointer-events'),pp=el.style.getPropertyPriority('pointer-events');el.style.setProperty('pointer-events','all','important');
   function on(x,y){if(x<0||y<0||x>=innerWidth||y>=innerHeight)return null;var t=document.elementFromPoint(x,y);return !!(t&&(t===el||el.contains(t)));}
   function cut(miss,hit,fix,horiz){for(var k=0;k<7;k++){var m=(miss+hit)/2;if(horiz?on(m,fix):on(fix,m))hit=m;else miss=m;}return hit;}
   var nx=Math.max(3,Math.min(24,Math.ceil((R-L)/6))),ny=Math.max(3,Math.min(10,Math.ceil((B-T)/5))),dx=(R-L)/nx,dy=(B-T)/ny,n=0,e=null;
   for(var i=0;i<nx;i++)for(var j=0;j<ny;j++){var x=L+(i+.5)*dx,y=T+(j+.5)*dy,o=on(x,y);if(o===null)continue;n++;if(!o)continue;
    if(!e)e={l:[i,x,y],r:[i,x,y],t:[j,x,y],b:[j,x,y]};
    if(i<e.l[0])e.l=[i,x,y];if(i>e.r[0])e.r=[i,x,y];if(j<e.t[0])e.t=[j,x,y];if(j>e.b[0])e.b=[j,x,y];}
   var h=null;if(e){h={L:e.l[0]?cut(e.l[1]-dx,e.l[1],e.l[2],true):L,R:e.r[0]<nx-1?cut(e.r[1]+dx,e.r[1],e.r[2],true):R,
    T:e.t[0]?cut(e.t[2]-dy,e.t[2],e.t[1],false):T,B:e.b[0]<ny-1?cut(e.b[2]+dy,e.b[2],e.b[1],false):B};}
   if(pv)el.style.setProperty('pointer-events',pv,pp);else el.style.removeProperty('pointer-events');sv.removeAttribute('data-look-pe');
   return n?(h||{none:true}):null;}
 function clipr(el,r,svg){var L=r.left,T=r.top,R=r.right,B=r.bottom,shp=false;for(var x=el;x&&x!==svg;x=x.parentNode){var cs=getComputedStyle(x);
   if(cs.clipPath&&cs.clipPath!=='none'&&cs.clipPath.indexOf('url(')<0)shp=true;
   [cs.clipPath,cs.maskImage||cs.webkitMaskImage].forEach(function(v){var m=/url\(["']?#([^"')]+)/.exec(v||'');if(!m)return;var cp=document.getElementById(m[1]);
    if(!cp||!x.getScreenCTM)return;var M=x.getScreenCTM(),u=null;Array.prototype.forEach.call(cp.children,function(c){if(!c.getBBox)return;var b=c.getBBox();
     u=u?{x0:Math.min(u.x0,b.x),y0:Math.min(u.y0,b.y),x1:Math.max(u.x1,b.x+b.width),y1:Math.max(u.y1,b.y+b.height)}:{x0:b.x,y0:b.y,x1:b.x+b.width,y1:b.y+b.height};});
    if(!u||cp.getAttribute('clipPathUnits')==='objectBoundingBox'||cp.getAttribute('maskContentUnits')==='objectBoundingBox')return;
    var P=[[u.x0,u.y0],[u.x1,u.y0],[u.x0,u.y1],[u.x1,u.y1]].map(function(q){return new DOMPoint(q[0],q[1]).matrixTransform(M);});
    L=Math.max(L,Math.min.apply(0,P.map(function(q){return q.x;})));R=Math.min(R,Math.max.apply(0,P.map(function(q){return q.x;})));
    T=Math.max(T,Math.min.apply(0,P.map(function(q){return q.y;})));B=Math.min(B,Math.max.apply(0,P.map(function(q){return q.y;})));});}
  if(shp&&R>L&&B>T){var hb=hitbox(el,L,T,R,B);   // inset()/polygon()/circle(): ask the browser's hit test
   if(hb&&hb.none)return {left:L,top:T,right:L,bottom:T,out:true};
   if(hb){L=Math.max(L,hb.L);T=Math.max(T,hb.T);R=Math.min(R,hb.R);B=Math.min(B,hb.B);}}
  return {left:L,top:T,right:Math.max(L,R),bottom:Math.max(T,B),out:R<L-0.5||B<T-0.5};}
 function ground(w){var cs=[];for(var x=w;x&&x.nodeType===1;x=x.parentNode)cs.push(col(getComputedStyle(x).backgroundColor));
  var g=[255,255,255];for(var i=cs.length-1;i>=0;i--){var c=cs[i];if(c&&c[3]>0)g=[0,1,2].map(function(k){return c[k]*c[3]+g[k]*(1-c[3]);});}return g;}
 [null].concat(times).forEach(function(t){setFrame(t);OUT.frames.push({t:t===null?'rest':t,frags:W.map(measure),nb:neighbours()});});
 if(CFG.pauses){OUT.pauses=[];OUT.ptimes=W.map(function(w){   // N reproducible in-between times per fragment, seeded from its name
   var nm=w.getAttribute('data-anim')||'',h=2166136261;for(var i=0;i<nm.length;i++){h^=nm.charCodeAt(i);h=Math.imul(h,16777619)>>>0;}
   function rnd(){h=(h+0x6D2B79F5)>>>0;var z=h;z=Math.imul(z^z>>>15,z|1);z^=z+Math.imul(z^z>>>7,z|61);return((z^z>>>14)>>>0)/4294967296;}
   var mk=[],c=parseFloat(w.getAttribute('data-anim-cycle'))||0;
   (w.getAttribute('data-anim-phases')||'').split(',').forEach(function(p){p=parseFloat(p);if(p>0)mk.push(p);});
   var last=mk.length?Math.max.apply(0,mk):c,out=[];if(c)mk.push(c);
   for(var k=0;k<500&&out.length<CFG.pauses;k++){var t=+(0.5+rnd()*(last-0.5)).toFixed(2);
    if(t<=0.5||t>=last||out.some(function(o){return Math.abs(o-t)<0.4;})||mk.some(function(m){return Math.abs(m-t)<0.15;}))continue;out.push(t);}
   return out.sort(function(a,b){return a-b;});});
  var all=[];OUT.ptimes.forEach(function(l){l.forEach(function(t){if(all.indexOf(t)<0)all.push(t);});});
  all.sort(function(a,b){return a-b;}).forEach(function(t){setFrame(t);OUT.pauses.push({t:t,frags:W.map(measure)});});}
 setFrame(null);OUT.ground=W.map(function(w){return CFG.page?ground(w):col(getComputedStyle(w).getPropertyValue('--anim-bg').trim())||ground(w);});
 var hs=document.createElement('style');   // the screenshot (accent share) sees the resting frame without scene ground
 hs.textContent='[data-anim-scene],[data-anim-scene] *{visibility:hidden!important}';document.head.appendChild(hs);
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


def chrome_cmd(chrome, win, *args):
    cmd = [chrome, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--window-size=%d,%d' % win] + list(args)
    if os.environ.get('CI') or (hasattr(os, 'geteuid') and os.geteuid() == 0):
        cmd.insert(1, '--no-sandbox')
    return cmd


def run_probe(chrome, html, base_dir, win, shot=True):
    """Run the probe page; with shot, the same Chrome run also screenshots the page as the probe leaves it
    (resting frame, scene ground hidden). Returns (data, image or None)."""
    d = tempfile.mkdtemp(prefix='check-look-')  # <base href> in the page resolves assets
    try:
        path, png = os.path.join(d, 'probe.html'), os.path.join(d, 'shot.png')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        args = (['--screenshot=' + png] if shot else []) + ['--dump-dom', 'file://' + path]
        dom = subprocess.run(chrome_cmd(chrome, win, *args), capture_output=True, text=True, timeout=120).stdout
        m = re.search(r'<script type="application/json" id="look">(.*?)</script>', dom, re.S)
        if shot and not (m and m.group(1).strip()):  # a Chrome that will not do both at once: probe alone
            return run_probe(chrome, html, base_dir, win, shot=False)
        img = None
        if shot:
            try:
                img = png_rows(png)
            except (OSError, ValueError, zlib.error, struct.error):
                img = None
    finally:
        shutil.rmtree(d, ignore_errors=True)
    if not m or not m.group(1).strip():
        raise RuntimeError('Chrome returned no measurement (probe did not run)')
    data = json.loads(m.group(1))
    if data.get('error'):
        raise RuntimeError('probe error: ' + data['error'].split('\n')[0])
    return data, img


def png_rows(path):
    """Decode an 8-bit RGB or RGBA, non-interlaced PNG (what Chrome writes) with zlib only: (w, h, bpp, rows).
    Sub and Up rows are undone on whole rows at once (bytewise add without carry on big ints), Average and
    Paeth byte by byte."""
    with open(path, 'rb') as f:
        d = f.read()
    if d[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not a PNG')
    pos, idat, hdr = 8, [], None
    while pos + 8 <= len(d):
        n, typ = struct.unpack('>I4s', d[pos:pos + 8])
        body = d[pos + 8:pos + 8 + n]
        pos += 12 + n
        if typ == b'IHDR':
            hdr = struct.unpack('>IIBBBBB', body)
        elif typ == b'IDAT':
            idat.append(body)
        elif typ == b'IEND':
            break
    if not hdr:
        raise ValueError('PNG without IHDR')
    w, h, bd, ct, _, _, il = hdr
    if bd != 8 or ct not in (2, 6) or il:
        raise ValueError('unsupported PNG (bit depth %d, colour type %d, interlace %d)' % (bd, ct, il))
    bpp = 4 if ct == 6 else 3
    st = w * bpp
    raw = zlib.decompress(b''.join(idat))
    if len(raw) < h * (st + 1):
        raise ValueError('truncated PNG data')
    lo, hi = int.from_bytes(b'\x7f' * st, 'big'), int.from_bytes(b'\x80' * st, 'big')

    def add(x, y):  # bytewise (x + y) mod 256 over the whole row
        return ((x & lo) + (y & lo)) ^ ((x ^ y) & hi)
    prev, rows = bytes(st), []
    for y in range(h):
        f, r = raw[y * (st + 1)], raw[y * (st + 1) + 1:(y + 1) * (st + 1)]
        if f == 0:
            cur = r
        elif f == 1:  # Sub: running sum along the row, by doubling shifts
            x, sh = int.from_bytes(r, 'big'), bpp
            while sh < st:
                x = add(x, x >> (8 * sh))
                sh *= 2
            cur = x.to_bytes(st, 'big')
        elif f == 2:  # Up
            cur = add(int.from_bytes(r, 'big'), int.from_bytes(prev, 'big')).to_bytes(st, 'big')
        elif f == 3:  # Average
            c = bytearray(r)
            for i in range(st):
                c[i] = (c[i] + ((c[i - bpp] if i >= bpp else 0) + prev[i]) // 2) & 255
            cur = bytes(c)
        elif f == 4:  # Paeth
            c = bytearray(r)
            for i in range(st):
                pa_, pb_ = (c[i - bpp], prev[i - bpp]) if i >= bpp else (0, 0)
                b_ = prev[i]
                pp = pa_ + b_ - pb_
                da, db, dc = abs(pp - pa_), abs(pp - b_), abs(pp - pb_)
                c[i] = (c[i] + (pa_ if da <= db and da <= dc else b_ if db <= dc else pb_)) & 255
            cur = bytes(c)
        else:
            raise ValueError('bad PNG row filter %d' % f)
        rows.append(cur)
        prev = cur
    return w, h, bpp, rows


def accent_share(img, box, g, tokc, step=2):
    """Accent share of the ink in screen box (x0, y0, x1, y1) of a decoded screenshot, sampling every step-th
    pixel both ways: (accent weight, ink weight). A pixel within 12 of the ground g is ground. A pixel on the
    straight blend from the ground to a token colour (within 20) is that token at its blend weight t (which
    covers antialiasing, faded copies and the glow); any other pixel is ink of weight 1, accent when the
    accent is its nearest token colour and within 64 of it."""
    acc = tokc.get('accent')
    if not acc:
        return None
    w, h, bpp, rows = img
    acc = tuple(acc[:3])
    toks = [(acc, True)] + [(tuple(c[:3]), False) for n, c in sorted(tokc.items())
                             if n not in ('accent', 'bg') and c and dist(c, g) >= 12 and dist(c, acc) >= 12]
    lines = []
    for c, isacc in toks:
        v = [c[i] - g[i] for i in range(3)]
        vv = sum(x * x for x in v)
        if vv > 0:
            lines.append((v, vv, c, isacc))
    cache = {}

    def classify(p):
        if dist(p, g) <= 12:
            return 0.0, 0.0
        best = None
        for v, vv, c, isacc in lines:
            t = max(0.0, min(1.0, sum((p[i] - g[i]) * v[i] for i in range(3)) / vv))
            res = dist(p, [g[i] + t * v[i] for i in range(3)])
            if best is None or res < best[0]:
                best = (res, t, isacc)
        if best and best[0] <= 20:
            return best[1], best[1] if best[2] else 0.0
        near = min(toks, key=lambda x: dist(p, x[0]))
        return 1.0, 1.0 if near[1] and dist(p, acc) <= 64 else 0.0
    x0, y0 = max(0, int(box[0])), max(0, int(box[1]))
    x1, y1 = min(w, int(math.ceil(box[2]))), min(h, int(math.ceil(box[3])))
    seen = {}
    for y in range(y0, y1, step * 4):  # the ground as painted: the most common colour, if it is common
        row = rows[y]
        for x in range(x0, x1, step * 4):
            k = row[x * bpp:x * bpp + 3]
            seen[k] = seen.get(k, 0) + 1
    if seen:
        k, n = max(seen.items(), key=lambda kv: kv[1])
        if n >= 0.3 * sum(seen.values()) and dist(tuple(k), g) > 12:
            g = tuple(k)
            lines = [([c[i] - g[i] for i in range(3)], sum((c[i] - g[i]) ** 2 for i in range(3)), c, isacc)
                     for c, isacc in toks if dist(c, g) >= 12]
    tot = a_ = 0.0
    for y in range(y0, y1, step):
        row = rows[y]
        for x in range(x0, x1, step):
            k = row[x * bpp:x * bpp + 3]
            r = cache.get(k)
            if r is None:
                r = cache[k] = classify(tuple(k))
            tot += r[0]
            a_ += r[1]
    return a_, tot


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
def contrast_bad(T, g, tok, a):
    """Labels under their contrast floor on ground g: [(ratio, message)], worst run per label."""
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
    return bad


def painted(e, g):
    """A visible element that puts ink on the ground (not an invisible hit area or a ground-coloured fill)."""
    if e['op'] <= 0.05 or e['glow'] or (e['w'] <= 0 and e['h'] <= 0):
        return False
    if e['tag'] == 'text':
        return True
    if e['stroke'] and e['sw'] > 0 and e['stroke'][3] * e['so'] * e['op'] > 0.05:
        return True
    return bool(e['fill']) and e['fill'][3] * e['fo'] * e['op'] > 0.05 and \
        dist(over(e['fill'], e['fill'][3] * e['fo'] * e['op'], g), g) >= 6


def gap_check(t, frames, fr, k, g, a, R, pre, per):
    """--page: the fragment's ink against the slide's own text and pictures, in screen px."""
    nb = next((f.get('nb') for f in frames if f['t'] == t), None)
    if not a.page or not nb:
        return
    m = fr['ctm']
    def scr(x, y):
        return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]
    floor = a.min_gap
    best, worst, hits = None, None, []
    when = 'rest' if t == 'rest' else '%gs' % t
    for e in fr['els']:
        if not painted(e, g):
            continue
        p, q = scr(e['x'], e['y']), scr(e['x'] + e['w'], e['y'] + e['h'])
        x0, x1, y0, y1 = min(p[0], q[0]), max(p[0], q[0]), min(p[1], q[1]), max(p[1], q[1])
        for n in nb:
            ix = min(x1, n['x'] + n['w']) - max(x0, n['x'])
            iy = min(y1, n['y'] + n['h']) - max(y0, n['y'])
            if ix > 2 and iy > 2:
                hits.append('%s covers the slide\'s "%s"' % (label(e), n['txt']))
                continue
            d = max(n['x'] - x1, x0 - (n['x'] + n['w']), n['y'] - y1, y0 - (n['y'] + n['h']), 0)
            if best is None or d < best:
                best, worst = d, (e, n)
    per.setdefault(t, {})['gap'] = best
    for h in sorted(set(hits))[:4]:
        R.fail(pre + 'gap', 'at %s: %s: keep the figure inside its slot, crop the viewBox or move the label' % (when, h))
    if best is not None and best < floor and not hits:
        R.warn(pre + 'gap', 'at %s: %s is %.0fpx from the slide\'s "%s" (< %gpx): give the slide content room '
               '(smaller viewBox, slot padding)' % (when, label(worst[0]), best, worst[1]['txt'], floor))
    elif best is not None and t == 'rest' and not hits:
        R.info(pre + 'gap', 'nearest slide content %.0fpx away at rest (floor %gpx)' % (best, floor))


def analyse(frames, k, gcol, a, R, pre, px=None, pauses=None, ptimes=None):
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
    per = {}  # per frame: elements clipped and label pairs overlapping in that frame
    for t, fr in F:
        cx0, cy0, cw, ch = clip
        pc = per.setdefault(t, {'clip': 0, 'overlap': 0})
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
            if ox > lim or oy > lim:
                pc['clip'] += 1
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
                if p['txt'] == q['txt'] and abs(p['y'] - q['y']) < 3 and abs(p['w'] - q['w']) <= 0.25 * max(p['w'], q['w']) \
                        and min(abs(p['x'] - q['x']), abs(p['x'] + p['w'] - q['x'] - q['w']),
                                abs(p['x'] + p['w'] / 2 - q['x'] - q['w'] / 2)) < 3:
                    continue  # a highlight twin drawn over its base label (same anchor; a bolder twin may be wider) reads as one
                if ix > 2 and iy > 2:
                    pc['overlap'] += 1
                if ix > 2 and iy > 2 and key not in overl:
                    overl[key] = '%s and %s overlap by %.0fx%.0f at %s' % (label(p), label(q), ix, iy, t if t == 'rest' else '%gs' % t)
    for m in clipped.values():
        R.fail(pre + 'clip', m + ': move it inside the viewBox, shorten the label or widen the viewBox')
    for m in overl.values():
        R.fail(pre + 'overlap', m + ': move one, stack them with more gap, or drop one')

    els = rest['els']
    T = [e for e in els if e['tag'] == 'text' and vis(e)]
    filled, scene = {}, {}
    for e in els:
        if e['tag'] != 'text' and e['fill'] and vis(e) and not e['glow']:
            al = e['fill'][3] * e['fo'] * e['op']
            comp = over(e['fill'], al, g)
            if al > 0.08 and dist(comp, g) >= 6:  # a ground-coloured fill is a label plate
                (scene if e.get('scene') else filled)[e['i']] = e
    if scene:  # data-anim-scene: the thing itself drawn, not a card; exempt from boxes and label-on-fill
        rings = 0
        for e in els:
            if e['tag'] == 'circle' and vis(e) and e['stroke'] and e['sw'] > 0 \
                    and e['i'] not in filled and e['i'] not in scene and e['w'] >= 16:
                if any(t['x'] + t['w'] / 2 > e['x'] and t['x'] + t['w'] / 2 < e['x'] + e['w'] and
                       t['y'] + t['h'] / 2 > e['y'] and t['y'] + t['h'] / 2 < e['y'] + e['h'] for t in T):
                    rings += 1
        msg = '%d filled shape(s) marked data-anim-scene, exempt from boxes and label-on-fill' % len(scene)
        if len(scene) > len(filled) and rings >= 3:
            R.warn(pre + 'scene', msg + '; with %d labelled rings this reads as a node diagram: data-anim-scene is for '
                   'the thing itself drawn (water, land, a wall), not for cards behind labels' % rings)
        else:
            R.info(pre + 'scene', msg)
    on_shape = sorted({ti for ti, si in rest['inside'] if si in filled and els[ti]['tag'] == 'text'})
    if on_shape:
        R.warn(pre + 'overlap', '%d label(s) sit on a filled shape: %s; put labels on the ground or on a plate in --anim-bg'
               % (len(on_shape), few([label(els[i]) for i in on_shape])))

    # 3 contrast (rest; every mark under --at-marks)
    bad = contrast_bad(T, g, tok, a)
    for c, m in sorted(bad)[:6]:
        R.fail(pre + 'contrast', m + ' on ground %s: use --anim-fg/--anim-muted, raise the opacity' % hexc(g))
    if len(bad) > 6:
        R.fail(pre + 'contrast', '%d more labels below their contrast floor' % (len(bad) - 6))
    faint, weak = [], []
    for e in els:
        if vis(e) and e['tag'] != 'text' and not e['glow'] and e['stroke'] and e['sw'] > 0 and dist(e['stroke'], g) >= 6:
            al = e['stroke'][3] * e['so'] * e['op']
            if al > 0.02:
                c = ratio(over(e['stroke'], al, g), g)
                if al > 0.5 and not e['dash'] and not e.get('scene'):  # a solid line that carries structure
                    if c < 3.0:
                        weak.append((c, e))
                elif c < 1.5 and not (e['dash'] and c >= 1.1):  # dotted gridlines may be fainter (style.md chart)
                    faint.append((c, e))
    if weak:
        weak.sort(key=lambda x: x[0])
        R.warn(pre + 'line-contrast', '[line-contrast] %d structure stroke(s) below 3:1 on ground %s, worst: %s; draw '
               'structure in --anim-line (3:1 on the ground), keep faint lines for dashed or faded decoration' % (
                   len(weak), hexc(g), few(['%s %s %.2f:1' % (label(e), hexc(e['stroke']), c) for c, e in weak])))
    if faint:
        faint.sort(key=lambda x: x[0])
        R.warn(pre + 'contrast', 'faint lines on this ground: %d stroke(s) below 1.5:1, faintest %.2f:1 (%s %s); darken '
               '--anim-line for this ground or raise faded opacities' % (len(faint), faint[0][0], label(faint[0][1]), hexc(faint[0][1]['stroke'])))

    # 3b accent area at rest, measured from the pixels of a screenshot of the resting frame (scene ground
    # hidden; see accent_share); without a screenshot, estimated from element geometry: fills by box area
    # (circles and ellipses x pi/4, paths x 0.5), strokes by length x width, text by 0.22 of its box (ink share of type)
    def ink(e, part):
        if part == 'fill':
            k = 1.0 if e['tag'] == 'rect' else math.pi / 4 if e['tag'] in ('circle', 'ellipse') else 0.5
            return e['w'] * e['h'] * k
        if part == 'text':
            return e['w'] * e['h'] * 0.22  # glyph ink of normal-weight type covers about a fifth to a quarter of its box
        ln = e.get('len') or 2 * (e['w'] + e['h'])
        return ln * max(e['sw'], 0.5)
    acc = tok.get('accent')
    tot = acc_ink = acc_out = 0.0  # acc_out: accent ink outside the focal element
    for e in els:
        if not vis(e) or (e['w'] <= 0 and e['h'] <= 0):
            continue
        parts = [('text', e['fill'], e['fo'])] if e['tag'] == 'text' else \
            [('fill', e['fill'], e['fo']), ('stroke', e['stroke'], e['so'] if e['sw'] > 0 else 0)]
        for part, c, o in parts:
            if not c or c[3] * o * e['op'] <= 0.05 or dist(over(c, c[3] * o * e['op'], g), g) < 6:
                continue
            a_ = ink(e, part) * min(1.0, c[3] * o * e['op'])  # a glow copy counts at its own opacity
            tot += a_
            if acc and dist(c, acc) < 24 and (e['glow'] or dist(over(c, c[3] * o * e['op'], g), acc) < 48):
                acc_ink += a_  # the accent as seen (a faint accent wash over the ground is not counted)
                if not e.get('focal'):
                    acc_out += a_
    if px and px[1] > 0 and acc:
        share = 100.0 * px[0] / px[1]
        out = 100.0 * acc_out / tot if tot > 0 else 100.0  # geometry estimate of the accent outside the focal element
        if share > 25 and out <= 8:
            R.info(pre + 'accent-area', 'accent %.1f %% of the ink at rest (measured from pixels), nearly all of it the '
                   'focal element itself (about %.0f %% elsewhere): the claim is the accent' % (share, out))
        elif share > 25:
            R.warn(pre + 'accent-area', '[accent-area] the accent covers %.1f %% of the ink at rest (rule: at most about a '
                   'fifth, measured from pixels): keep the accent on the focal element and the active path; when the '
                   'story has reached every part, let the reached parts settle to --anim-fg' % share)
        else:
            R.info(pre + 'accent-area', 'accent %.1f %% of the ink at rest (measured from pixels)' % share)
    elif tot > 0 and acc:
        share = 100.0 * acc_ink / tot
        if share > 25:  # the rule is about 10 %; the geometry estimate runs high on hairline figures
            R.warn(pre + 'accent-area', '[accent-area] the accent covers about %.0f %% of the drawn area at rest (rule about '
                   '10 %%, estimated from element geometry, no screenshot): keep the accent on the active and reached parts, the rest in '
                   '--anim-line and --anim-muted' % share)
        else:
            R.info(pre + 'accent-area', 'accent about %.0f %% of the drawn area at rest (estimated from element geometry, no screenshot)' % share)

    # 3c focal element (data-anim-focal) at rest
    foc = [e for e in els if e.get('focal')]
    if foc:
        fv = [e for e in foc if vis(e)]
        if not fv:
            R.warn(pre + 'focal', '[focal] the data-anim-focal element is not visible in the resting frame: the focal '
                   'element is what the eye lands on at rest')
        else:
            ft = [e for e in fv if e['tag'] == 'text']
            others_t = sorted(e['px'] for e in T if not e.get('focal'))
            if ft and others_t:
                med = others_t[len(others_t) // 2]
                big = max(e['px'] for e in ft)
                if big < 1.5 * med - 0.05:
                    R.warn(pre + 'focal', '[focal] focal text %s renders at %.1fpx, under 1.5x the median text (%.1fpx): '
                           'make it the hero size or move data-anim-focal' % (label(max(ft, key=lambda e: e['px'])), big, med))
            elif not ft:
                fs = [e for e in fv if e['w'] >= 2 and e['h'] >= 2]
                peers = sorted(e['w'] * e['h'] for e in els if vis(e) and e['tag'] not in ('text', 'use') and not e.get('focal')
                               and not e.get('scene') and not e['glow'] and e['w'] >= 2 and e['h'] >= 2 and painted(e, g))
                if fs and peers:
                    fx0, fy0 = min(e['x'] for e in fs), min(e['y'] for e in fs)
                    fx1, fy1 = max(e['x'] + e['w'] for e in fs), max(e['y'] + e['h'] for e in fs)
                    med = peers[len(peers) // 2]
                    # the focal shape stands out when any one holds: its box is at least the median shape box; its
                    # stroke is the heaviest (ties allowed) or at least 1.5x the median stroke; it carries the only
                    # glow at rest; or it is a group holding hero-size text (1.5x the median text)
                    def stroked(e):
                        return e['tag'] not in ('text', 'use') and e['sw'] > 0 and e['stroke'] and e['so'] > 0
                    fsw = max([e['sw'] for e in fv if stroked(e)] or [0])
                    osw = sorted(e['sw'] for e in els if vis(e) and stroked(e) and not e.get('focal') and not e.get('scene'))
                    heavy = fsw > 0 and (not osw or fsw >= osw[-1] - 0.01 or fsw >= 1.5 * osw[len(osw) // 2])
                    glow = any(e['glow'] for e in fv) and not any(e['glow'] for e in els if vis(e) and not e.get('focal'))
                    hero = bool(ft) and bool(others_t) and max(e['px'] for e in ft) >= 1.5 * others_t[len(others_t) // 2] - 0.05
                    if (fx1 - fx0) * (fy1 - fy0) < med and not (heavy or glow or hero):
                        R.warn(pre + 'focal', '[focal] the focal shape (%.0f x %.0f) is smaller than the median shape box '
                               '(%.0f units^2), and neither its stroke (heaviest or 1.5x the median), the only glow nor '
                               'hero text sets it apart: make it visibly larger or heavier than its peers' % (
                                   fx1 - fx0, fy1 - fy0, med))

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
    ink_els = [e for e in els if painted(e, g)]
    if ink_els:
        cx0, cy0, cw, ch = clip
        fw = (min(cx0 + cw, max(e['x'] + e['w'] for e in ink_els)) - max(cx0, min(e['x'] for e in ink_els))) / cw
        fh = (min(cy0 + ch, max(e['y'] + e['h'] for e in ink_els)) - max(cy0, min(e['y'] for e in ink_els))) / ch
        if fw < 0.6 and fh < 0.6:
            R.warn(pre + 'density', '[density] the drawn figure spans %.0f %% of the %s width and %.0f %% of its height '
                   '(< 60 %% both ways): pick a viewBox that fits the picture (layouts.md) or draw it larger'
                   % (100 * fw, 'slot' if a.slot or a.page else 'viewBox', 100 * fh))
    if len(T) > 40:
        R.warn(pre + 'density', '%d visible text elements at rest: drop labels before shrinking type' % len(T))

    # 7 smallest rendered text
    small = sorted((e['px'], label(e)) for e in T)
    under = [x for x in small if x[0] < floor - 0.05]
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

    # 10 gap to the slide's own content (--page): rest, and every mark under --at-marks
    for t, fr in F if a.at_marks else F[:1]:
        gap_check(t, frames, fr, k, g, a, R, pre, per)

    # 12 --at-pauses: clip, overlap and text floor at N in-between times, tolerant of mid-motion states
    if pauses is not None:
        pause_check(pauses, ptimes or [], k, clip, floor, clipped, overl, a, R, pre)

    # 11 the same rendered checks at every phase mark (--at-marks), one summary line per mark
    if not a.at_marks:
        return
    def key(m):  # the label a contrast message is about
        return m.split('" ')[0]
    said_c = {key(m) for _, m in bad}
    said_t = {lb for _, lb in under}
    for t, fr in F[1:]:
        Tm = [e for e in fr['els'] if e['tag'] == 'text' and vis(e)]
        badm = contrast_bad(Tm, g, tok, a)
        for c, m in sorted(x for x in badm if key(x[1]) not in said_c)[:6]:
            said_c.add(key(m))
            R.fail(pre + 'contrast', 'at %gs: %s on ground %s: a label shown at a mark must be readable; raise its '
                   'opacity or colour, or set the mark at a settled moment' % (t, m, hexc(g)))
        smallm = [e for e in Tm if e['px'] < floor - 0.05]
        for e in [x for x in smallm if label(x) not in said_t][:5]:
            said_t.add(label(e))
            R.fail(pre + 'text-size', 'at %gs: %s renders at %.1fpx < floor %gpx: a scaled or zoomed label must stay '
                   'above the floor' % (t, label(e), e['px'], floor))
        pc = per.get(t, {})
        gp = pc.get('gap')
        R.info(pre + 'marks', 'at %gs: clip %d, overlap %d, contrast %d, text-size %d%s' % (
            t, pc.get('clip', 0), pc.get('overlap', 0), len(badm), len(smallm),
            '' if gp is None else ', gap %.0fpx' % gp))


def pause_check(pauses, times, k, clip, floor, clipped, overl, a, R, pre):
    """WARN-only checks at in-between times: ink outside the viewBox (or slot), two labels overlapping, text
    under the floor. Elements under opacity 0.15 are skipped, and two labels overlap only when both are at
    0.6 or more (a cross-fade is intended). Findings already reported at rest or a mark are not repeated."""
    if not times:
        R.info(pre + 'pause', '[pause] no in-between times: the last phase mark is too close to 0.5 s')
        return
    R.info(pre + 'pause', '[pause] checked at %s (seeded from the fragment name)' % ', '.join('%gs' % t for t in times))
    by_t = dict((p['t'], p['frags'][k]) for p in pauses)
    cx0, cy0, cw, ch = clip
    said_c, said_o, said_s = set(clipped), set(overl), set()
    for t in times:
        fr = by_t.get(t)
        if not fr:
            continue
        E = [e for e in fr['els'] if e['op'] >= 0.15 and (e['w'] > 0 or e['h'] > 0) and not e['glow']]
        out = []
        for e in E:
            pad = e['sw'] / 2 if e['tag'] != 'text' and e['stroke'] and e['stroke'][3] > 0 else 0
            ox = max(cx0 - (e['x'] - pad), (e['x'] + e['w'] + pad) - (cx0 + cw), 0)
            oy = max(cy0 - (e['y'] - pad), (e['y'] + e['h'] + pad) - (cy0 + ch), 0)
            if e['tag'] != 'text':
                ox = 0 if e['h'] >= 0.25 * ch else ox
                oy = 0 if e['w'] >= 0.25 * cw else oy
            if max(ox, oy) > (1 if e['tag'] == 'text' else 2) and e['i'] not in said_c:
                said_c.add(e['i'])
                out.append('%s sticks out of the %s by %.0f units' % (label(e), 'slot' if a.slot or a.page else 'viewBox', max(ox, oy)))
        T = [e for e in E if e['tag'] == 'text']
        ovl = []
        for i in range(len(T)):
            for j in range(i + 1, len(T)):
                p, q = T[i], T[j]
                if p['op'] < 0.6 or q['op'] < 0.6 or (p['i'], q['i']) in said_o:
                    continue  # a cross-fade: one label leaves while the other arrives
                if p['txt'] == q['txt'] and abs(p['y'] - q['y']) < 3 and abs(p['w'] - q['w']) <= 0.25 * max(p['w'], q['w']) \
                        and min(abs(p['x'] - q['x']), abs(p['x'] + p['w'] - q['x'] - q['w']),
                                abs(p['x'] + p['w'] / 2 - q['x'] - q['w'] / 2)) < 3:
                    continue  # a highlight twin over its base label
                ip, iq = 0.15 * p['h'], 0.15 * q['h']
                ix = min(p['x'] + p['w'], q['x'] + q['w']) - max(p['x'], q['x'])
                iy = min(p['y'] + p['h'] - ip, q['y'] + q['h'] - iq) - max(p['y'] + ip, q['y'] + iq)
                if ix > 2 and iy > 2:
                    said_o.add((p['i'], q['i']))
                    ovl.append('%s and %s overlap by %.0fx%.0f' % (label(p), label(q), ix, iy))
        small = []
        for e in T:
            if e['px'] < floor - 0.05 and e['i'] not in said_s:
                said_s.add(e['i'])
                small.append('%s renders at %.1fpx < floor %gpx' % (label(e), e['px'], floor))
        for m in out[:4]:
            R.warn(pre + 'pause', '[pause] at %gs: %s (clip): keep moving parts inside the viewBox' % (t, m))
        for m in ovl[:4]:
            R.warn(pre + 'pause', '[pause] at %gs: %s (overlap): stagger them or move one aside while both show' % (t, m))
        for m in small[:4]:
            R.warn(pre + 'pause', '[pause] at %gs: %s (text-size): a growing label must stay above the floor '
                   'while it is readable' % (t, m))
    R.info(pre + 'pause', '[pause] orphan labels (a label shown before or without its shape) are not checked: '
           'look at the in-between frames')


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
    ap.add_argument('--at-marks', action='store_true',
                    help='also run contrast, text-size and gap at every phase mark; one summary line per mark')
    ap.add_argument('--at-pauses', type=int, nargs='?', const=3, default=None, metavar='N',
                    help='also check clip, overlap and text floor at N (default 3) reproducible in-between times '
                    '(WARN only)')
    ap.add_argument('--min-gap', type=float, metavar='PX',
                    help='page mode: clearance to the slide\'s own content (default 24 px at a 1920 window)')
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
    if a.at_pauses is not None and a.at_pauses < 1:
        ap.error('--at-pauses N needs N >= 1')
    cfg = {'gate': a.gate, 'page': a.slide if a.page else 0, 'pauses': a.at_pauses or 0}
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
        data, img = run_probe(chrome, html, base_dir, win)
    except (RuntimeError, subprocess.TimeoutExpired, ValueError) as e:
        print('error: %s' % e, file=sys.stderr); sys.exit(2)
    if a.stage_width is None:
        a.stage_width = data.get('stage') if a.page and data.get('stage') else 1920.0
    if a.min_text is None:
        a.min_text = round(max(10.0, 18 * a.stage_width / 1920), 2)
    if a.min_gap is None:
        a.min_gap = round(24.0 * (data.get('stage') or 1920) / 1920, 1)
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
        px = None
        if img:
            fr = frames[0]['frags'][k]
            m, (vx, vy, vw, vh) = fr['ctm'], fr['vb']
            P = [(m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]) for x, y in
                 ((vx, vy), (vx + vw, vy), (vx, vy + vh), (vx + vw, vy + vh))]
            box = (min(p[0] for p in P), min(p[1] for p in P), max(p[0] for p in P), max(p[1] for p in P))
            if box[0] >= -1 and box[1] >= -1 and box[2] <= img[0] + 1 and box[3] <= img[1] + 1:  # on screen
                px = accent_share(img, box, gcol[:3], fr['tokc'])
        analyse(frames, k, gcol, a, R, pre, px=px, pauses=data.get('pauses') if a.at_pauses else None,
                ptimes=(data.get('ptimes') or [[]] * nfr)[k] if a.at_pauses else None)
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
