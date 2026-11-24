"""Tests for scripts/build_gallery.py: the built gallery index, the per-entry playable demo pages
and the raw fragment copies. Runs the real build into a temp folder and tests the produced files.

  python3 -m unittest discover -s tests -v

The rendered checks drive headless Chrome over the DevTools protocol on a pipe (stdlib only). They
are skipped with a message when no Chrome/Chromium/Edge is found; set CHROME=/path/to/chrome.
"""
import importlib.util
import json
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'scripts', 'build_gallery.py')
POOL = os.path.join(ROOT, 'pool')
QUESTION = 'When the payment provider goes down, can orders still go through?'

_spec = importlib.util.spec_from_file_location('build_gallery', SCRIPT)
bg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bg)

TMP = None
SITE = None


def setUpModule():
    global TMP, SITE
    TMP = tempfile.mkdtemp(prefix='test-gallery-')
    SITE = os.path.join(TMP, 'site')
    r = subprocess.run([sys.executable, SCRIPT, '-o', SITE], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError('build_gallery.py failed:\n' + r.stdout + r.stderr)


def tearDownModule():
    if TMP:
        shutil.rmtree(TMP, ignore_errors=True)


def pool_names():
    return sorted(d for d in os.listdir(POOL) if os.path.isfile(os.path.join(POOL, d, f'{d}.html')))


def read(path, binary=False):
    with open(path, 'rb' if binary else 'r', **({} if binary else {'encoding': 'utf-8', 'newline': ''})) as f:
        return f.read()


# ------------------------------------------------------------------------------ static checks
class IndexPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = read(os.path.join(SITE, 'index.html'))

    def test_featured_block_before_grid(self):
        h = self.html
        self.assertIn(QUESTION, h)
        feat = h.index('id="featured"')
        grid = h.index('<section class="grid">')
        self.assertLess(feat, h.index(QUESTION))
        self.assertLess(h.index(QUESTION), grid)
        self.assertLess(h.index('id="fit-featured"'), grid)

    def test_featured_actions(self):
        block = self.html[self.html.index('id="featured"'):self.html.index('<section class="grid">')]
        for label in ('>Replay<', '>Copy prompt<', '>Download playable demo<', '>Copy embeddable HTML<', '>Link<'):
            self.assertIn(label, block)
        self.assertIn('data-copylink="featured"', block)
        self.assertIn('href="service-deps/service-deps-demo.html" download', block)
        self.assertIn(bg.esc(bg.FEATURED['answer'].partition(' ')[2]), block)

    def test_search_and_filters(self):
        self.assertRegex(self.html, r'<input class="search" id="q" type="search"')
        for g in ('verb', 'archetype', 'domain'):
            self.assertIn(f'data-group="{g}"', self.html)

    def test_every_entry_listed(self):
        names = pool_names()
        self.assertGreater(len(names), 10)
        for n in names:
            self.assertIn(f'<a href="{n}/index.html">{n}</a>', self.html, n)


class DemoPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = read(os.path.join(SITE, 'service-deps', 'service-deps-demo.html'))

    def test_no_network_resource_loads(self):
        h = self.html
        self.assertNotRegex(h, r'(?i)<link\b')
        self.assertNotRegex(h, r'(?i)<script\b[^>]*\bsrc\s*=')
        self.assertNotRegex(h, r'(?i)\bsrc\s*=\s*["\']?\s*(https?:)?//')
        self.assertNotRegex(h, r'(?i)@import')
        self.assertNotRegex(h, r'(?i)url\(\s*["\']?\s*(https?:)?//')
        # every remaining http(s) string is an XML namespace or a plain text link
        for m in re.finditer(r'https?://', h):
            before = h[max(0, m.start() - 40):m.start()]
            ok = re.search(r'xmlns(:\w+)?="$', before) or re.search(r'<a href="$', before)
            self.assertTrue(ok, f'http(s) reference that is not a namespace or <a href>: ...{h[m.start() - 40:m.start() + 60]}')
        self.assertIn('<a href="https://github.com/', h)

    def test_contains_fragment_unchanged(self):
        self.assertIn(read(os.path.join(POOL, 'service-deps', 'service-deps.html')), self.html)

    def test_replay_control(self):
        self.assertRegex(self.html, r'<button type="button" id="replay">Replay</button>')

    def test_reduced_motion_and_print_rules(self):
        h = self.html
        rm = h[h.index('@media (prefers-reduced-motion: reduce)'):]
        self.assertIn('animation:none !important', rm[:200])
        pr = h[h.index('@media print'):]
        pr = pr[:pr.index('\n}\n')]
        self.assertIn('animation:none !important', pr)
        self.assertRegex(pr, r'\.bar[^{]*\{display:none !important\}')
        self.assertIn("beforeprint", h)


class EveryEntry(unittest.TestCase):
    def test_demo_file_and_raw_copy(self):
        for n in pool_names():
            with self.subTest(n=n):
                demo = os.path.join(SITE, n, f'{n}-demo.html')
                self.assertTrue(os.path.isfile(demo))
                self.assertEqual(read(os.path.join(SITE, n, f'{n}.html'), True),
                                 read(os.path.join(POOL, n, f'{n}.html'), True))
                detail = read(os.path.join(SITE, n, 'index.html'))
                self.assertIn(f'href="{n}-demo.html" download>Download playable demo<', detail)
                self.assertIn('>Copy embeddable HTML<', detail)

    def test_demo_cli_and_function(self):
        frag = os.path.join(POOL, 'service-deps', 'service-deps.html')
        out = os.path.join(TMP, 'cli', 'x.html')
        r = subprocess.run([sys.executable, SCRIPT, '--demo', frag, '-o', out, '--title', 'T', '--story', 'S'],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = read(out)
        self.assertIn(read(frag), page)
        self.assertIn('<h1>T</h1>', page)
        self.assertIn('<p class="story">S</p>', page)
        self.assertIn('id="replay"', bg.demo_page('x', '<div></div>', 'X', '', ''))


# ------------------------------------------------------------------------------ headless Chrome
def find_chrome():
    for c in [os.environ.get('CHROME'),
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


class CDP:
    """A minimal DevTools protocol client over --remote-debugging-pipe (fd 3 in, fd 4 out)."""

    def __init__(self, chrome):
        import fcntl
        self.prof = tempfile.mkdtemp(prefix='cdp-')
        a_r, self.w = os.pipe()     # we write, Chrome reads on fd 3
        self.r, b_w = os.pipe()     # Chrome writes on fd 4, we read

        def child():
            x = fcntl.fcntl(a_r, fcntl.F_DUPFD, 10)
            y = fcntl.fcntl(b_w, fcntl.F_DUPFD, 10)
            os.dup2(x, 3)
            os.dup2(y, 4)
        cmd = [chrome, '--headless=new', '--remote-debugging-pipe', '--user-data-dir=' + self.prof,
               '--no-first-run', '--no-default-browser-check', '--disable-gpu', '--hide-scrollbars',
               '--disable-extensions', '--disable-background-networking', '--disable-component-update',
               '--disable-sync', '--metrics-recording-only', '--no-pings', '--mute-audio', 'about:blank']
        if os.environ.get('CI') or (hasattr(os, 'geteuid') and os.geteuid() == 0):
            cmd.insert(1, '--no-sandbox')
        # os.pipe() ends are close-on-exec, so only the dup2'd fds 3 and 4 reach Chrome
        self.p = subprocess.Popen(cmd, preexec_fn=child, close_fds=False,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(a_r)
        os.close(b_w)
        self.buf, self.n, self.events, self.sid = b'', 0, [], None
        tid = self.call('Target.createTarget', {'url': 'about:blank'}, browser=True)['targetId']
        self.sid = self.call('Target.attachToTarget', {'targetId': tid, 'flatten': True}, browser=True)['sessionId']
        for d in ('Page', 'Network', 'Runtime', 'Animation'):
            self.call(d + '.enable')

    def _recv(self, timeout):
        end = time.time() + timeout
        while b'\0' not in self.buf:
            left = end - time.time()
            if left <= 0 or not select.select([self.r], [], [], left)[0]:
                raise TimeoutError('no reply from Chrome')
            chunk = os.read(self.r, 1 << 20)
            if not chunk:
                raise RuntimeError('Chrome closed the pipe')
            self.buf += chunk
        msg, self.buf = self.buf.split(b'\0', 1)
        return json.loads(msg)

    def call(self, method, params=None, browser=False, timeout=30):
        self.n += 1
        msg = {'id': self.n, 'method': method, 'params': params or {}}
        if self.sid and not browser:
            msg['sessionId'] = self.sid
        os.write(self.w, json.dumps(msg).encode() + b'\0')
        while True:
            m = self._recv(timeout)
            if m.get('id') == self.n:
                if 'error' in m:
                    raise RuntimeError(f'{method}: {m["error"]}')
                return m.get('result', {})
            self.events.append(m)

    def wait_event(self, name, timeout=30):
        end = time.time() + timeout
        while True:
            for i, m in enumerate(self.events):
                if m.get('method') == name:
                    return self.events.pop(i)
            self.events.append(self._recv(max(0.01, end - time.time())))

    def pump(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            try:
                self.events.append(self._recv(end - time.time()))
            except TimeoutError:
                break

    def goto(self, url):
        self.events = [m for m in self.events if m.get('method') != 'Page.loadEventFired']
        self.call('Page.navigate', {'url': url})
        self.wait_event('Page.loadEventFired')

    def js(self, expr):
        r = self.call('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
        if 'exceptionDetails' in r:
            raise RuntimeError('page error: ' + json.dumps(r['exceptionDetails'])[:400])
        return r['result'].get('value')

    def requests(self):
        return [m['params']['request']['url'] for m in self.events if m.get('method') == 'Network.requestWillBeSent']

    def close(self):
        try:
            self.call('Browser.close', browser=True, timeout=5)
        except Exception:
            pass
        try:
            self.p.wait(10)
        except subprocess.TimeoutExpired:
            self.p.kill()
        for fd in (self.r, self.w):
            try:
                os.close(fd)
            except OSError:
                pass
        shutil.rmtree(self.prof, ignore_errors=True)


# measures every <text> in the demo figure: effective opacity (with ancestors), inside the viewBox
PROBE = r"""(function(){var f=document.getElementById('fig'),svg=f.querySelector('svg'),vb=svg.viewBox.baseVal,
 S=svg.getScreenCTM().inverse(),out=[];
 svg.querySelectorAll('text').forEach(function(t){var op=1,shown=true;
  for(var x=t;x&&x!==f.parentNode;x=x.parentNode){var c=getComputedStyle(x);
   if(c.display==='none'||c.visibility==='hidden')shown=false;op*=parseFloat(c.opacity);}
  var r=t.getBoundingClientRect(),p=new DOMPoint(r.left,r.top).matrixTransform(S),q=new DOMPoint(r.right,r.bottom).matrixTransform(S);
  out.push({txt:t.textContent.trim(),op:shown?+op.toFixed(3):0,
   inside:p.x>=vb.x-1&&p.y>=vb.y-1&&q.x<=vb.x+vb.width+1&&q.y<=vb.y+vb.height+1});});
 var an=document.getAnimations();
 return {texts:out,visible:f.classList.contains('visible'),
  running:an.filter(function(a){return a.playState==='running'}).length,
  times:an.map(function(a){return a.currentTime}),
  replayShown:document.getElementById('replay').getClientRects().length>0};})()"""

FINAL_LABELS = ['Payments', 'Payment provider', 'DOWN', 'DEGRADED', 'blast radius', 'Orders', 'Orders DB',
                'Event bus', 'API gateway', 'Web app', 'Provider down: only Payments degrades, orders keep flowing']


def shown(state):
    return sorted(t['txt'] for t in state['texts'] if t['op'] > 0.05)


@unittest.skipIf(find_chrome() is None, 'no Chrome/Chromium/Edge found; set CHROME=/path/to/chrome to run the rendered checks')
class RenderedDemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cdp = CDP(find_chrome())
        cls.url = 'file://' + os.path.join(SITE, 'service-deps', 'service-deps-demo.html')

    @classmethod
    def tearDownClass(cls):
        cls.cdp.close()

    def setUp(self):
        c = self.cdp
        c.call('Emulation.setEmulatedMedia', {'media': '', 'features': []})
        c.call('Emulation.clearDeviceMetricsOverride')
        c.call('Animation.setPlaybackRate', {'playbackRate': 1})

    FRAME = r"""(function(){var s=document.querySelector('.scroll'),R=s.getBoundingClientRect(),cs=getComputedStyle(s);
     function box(txt){var t=Array.prototype.filter.call(document.querySelectorAll('#fig text'),function(x){
       return x.textContent.trim()===txt})[0],r=t.getBoundingClientRect();return [r.left,r.right]}
     return {frame:[R.left,R.right],down:box('DOWN'),deg:box('DEGRADED'),inner:innerWidth,
      over:s.scrollWidth-s.clientWidth,left:s.scrollLeft,fl:s.classList.contains('fl'),fr:s.classList.contains('fr'),
      mask:cs.maskImage||cs.webkitMaskImage}})()"""

    def test_6_mobile_frame_opens_on_the_outage(self):
        c = self.cdp
        c.call('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 2, 'mobile': True})
        self.finished()
        m = c.js(self.FRAME)
        self.assertEqual(m['inner'], 390)
        self.assertGreater(m['over'], 0, 'the figure should scroll inside its frame at 390 px')
        fade = 16    # the clipped-edge fade; the labels must sit in the clear part of the frame
        for k in ('down', 'deg'):
            self.assertGreaterEqual(m[k][0], m['frame'][0] + fade, f'{k} label cut on the left: {m}')
            self.assertLessEqual(m[k][1], m['frame'][1] - fade, f'{k} label cut on the right: {m}')
        self.assertTrue(m['fl'] and m['fr'], 'both clipped edges should fade')
        self.assertIn('gradient', m['mask'])
        start = m['left']
        c.js("document.querySelector('.scroll').scrollLeft=0")
        c.js("document.getElementById('replay').click()")
        self.assertAlmostEqual(c.js(self.FRAME)['left'], start, delta=1, msg='Replay should return to the focus')

    def test_7_desktop_and_print_no_scroll_no_fade(self):
        c = self.cdp
        c.call('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
        self.finished()
        m = c.js(self.FRAME)
        self.assertLessEqual(m['over'], 1)
        self.assertFalse(m['fl'] or m['fr'])
        c.call('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 2, 'mobile': True})
        c.call('Emulation.setEmulatedMedia', {'media': 'print'})
        m = c.js(self.FRAME)
        self.assertEqual(m['mask'], 'none', 'no fade in print')
        self.assertLessEqual(m['over'], 1, 'no scroll in print')

    def finished(self):
        """Load the demo at 10x speed and wait until the pass has ended."""
        c = self.cdp
        c.call('Animation.setPlaybackRate', {'playbackRate': 10})
        c.goto(self.url)
        for _ in range(100):
            st = c.js(PROBE)
            if st['visible'] and st['running'] == 0:
                return st
            c.pump(0.1)
        self.fail('the pass did not end')

    def resting(self):
        c = self.cdp
        c.call('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]})
        c.goto(self.url)
        return c.js(PROBE)

    def test_1_finished_frame_readable(self):
        st = self.finished()
        vis = shown(st)
        for lbl in FINAL_LABELS:
            self.assertIn(lbl, vis)
        for t in st['texts']:
            if t['op'] > 0.05:
                self.assertTrue(t['inside'], f'{t["txt"]!r} lies outside the viewBox')
        self.assertEqual(vis, shown(self.resting()), 'the finished pass differs from the resting frame')

    def test_2_reduced_motion_shows_finished_figure_at_once(self):
        st = self.resting()
        self.assertFalse(st['visible'], 'the gate should not be set under reduced motion')
        self.assertEqual(st['running'], 0)
        for lbl in FINAL_LABELS:
            self.assertIn(lbl, shown(st))
        self.assertTrue(all(t['inside'] for t in st['texts'] if t['op'] > 0.05))

    def test_3_print_shows_resting_frame_without_replay(self):
        c = self.cdp
        rest = shown(self.resting())
        c.call('Emulation.setEmulatedMedia', {'media': '', 'features': []})
        c.goto(self.url)
        c.pump(1.2)                                   # mid-pass: provider not down yet
        mid = c.js(PROBE)
        self.assertGreater(mid['running'], 0)
        self.assertNotIn('DEGRADED', shown(mid))
        self.assertTrue(mid['replayShown'])
        c.call('Emulation.setEmulatedMedia', {'media': 'print'})
        c.js("window.dispatchEvent(new Event('beforeprint'))")   # what the browser fires before printing
        st = c.js(PROBE)
        self.assertEqual(shown(st), rest)
        self.assertEqual(st['running'], 0)
        self.assertFalse(st['replayShown'], 'the Replay button is displayed in print')
        pdf = c.call('Page.printToPDF', {'landscape': True})
        self.assertGreater(len(pdf.get('data', '')), 1000)

    def test_4_replay_restarts_the_pass(self):
        c = self.cdp
        st = self.finished()
        self.assertTrue(st['times'] and min(st['times']) >= 9000)
        c.call('Animation.setPlaybackRate', {'playbackRate': 1})
        c.js("document.getElementById('replay').scrollIntoView({block:'center'})")
        box = c.js("(function(){var r=document.getElementById('replay').getBoundingClientRect();"
                   "return [r.left+r.width/2,r.top+r.height/2]})()")
        for t in ('mousePressed', 'mouseReleased'):
            c.call('Input.dispatchMouseEvent', {'type': t, 'x': box[0], 'y': box[1], 'button': 'left', 'clickCount': 1})
        after = c.js(PROBE)
        self.assertTrue(after['visible'])
        self.assertGreater(after['running'], 0, 'nothing plays after Replay')
        self.assertLess(max(after['times']), 1500, f'animations did not go back to the start: {max(after["times"])} ms')

    def test_5_no_network_requests(self):
        c = self.cdp
        c.events = []
        self.finished()
        c.call('Emulation.setEmulatedMedia', {'media': 'print'})
        c.pump(0.3)
        urls = c.requests()
        self.assertTrue(any(u.startswith('file:') for u in urls), 'request log is empty: the monitor saw nothing')
        bad = [u for u in urls if not u.startswith(('file:', 'data:', 'about:'))]
        self.assertEqual(bad, [])
        # control: the same monitor does see a remote load
        probe = os.path.join(TMP, 'net-control.html')
        with open(probe, 'w') as f:
            f.write('<!doctype html><link rel="stylesheet" href="https://example.invalid/x.css"><p>x')
        c.events = []
        c.goto('file://' + probe)
        c.pump(0.3)
        self.assertTrue(any(u.startswith('https://example.invalid') for u in c.requests()))


@unittest.skipIf(find_chrome() is None, 'no Chrome/Chromium/Edge found; set CHROME=/path/to/chrome to run the rendered checks')
class RenderedIndex(unittest.TestCase):
    def test_copy_sources_match(self):
        c = CDP(find_chrome())
        try:
            c.goto('file://' + os.path.join(SITE, 'index.html'))
            src = c.js("document.getElementById('src-featured').value")
            prompt = c.js("document.getElementById('prompt-featured').value")
            playing = c.js("document.getElementById('fit-featured').classList.contains('visible')")
        finally:
            c.close()
        self.assertEqual(src, read(os.path.join(POOL, 'service-deps', 'service-deps.html')))
        self.assertEqual(prompt, bg.FEATURED['prompt'])
        self.assertTrue(playing)


if __name__ == '__main__':
    unittest.main()
