#!/usr/bin/env python3
"""Export a deck to PDF, one slide per Letter or A4 landscape page, and prove that every
label in the deck is on its page.

Usage:
  export_pdf.py DECK.html [--paper letter|a4|both] [--out DIR] [--stage WxH|fluid]
                [--slides SELECTOR] [--source STATIC.html] [--min-pt N] [--chrome PATH]
                [--during-title TEXT] [--source-title TEXT]

  --paper    paper size, landscape (default: both; writes DECK-letter.pdf and DECK-a4.pdf)
  --out      folder for the PDFs (default: next to the deck)
  --stage    the deck's fixed slide size in px, e.g. 1920x1080, or 'fluid' for a deck whose
             slides follow the viewport. Default: read from the deck's own print rules
             (@page size, or a px width and height on the slide rule); fluid when none is found
  --slides   CSS selector of one slide (default: '.slide' when the deck uses that class, else
             'section')
  --source   the deck before figures were added (the static deck). Every label of a static
             slide must be on the same page of this deck's PDF, in the source's words
  --min-pt   warn when a label is smaller than this on paper (default 6 pt)

The deck file is not changed. The script prints from a temporary copy that carries one extra
print rule: the page size, and a scale that fits a whole slide on the page (a fixed stage is
scaled down and centred; a fluid slide takes the page). Animations show their resting frame
because of each fragment's print guard (integrate_fragment.py).

A resting frame cannot show what was on screen only during the pass (step captions that
cross-fade, a state label that changes). The script finds those labels (in the HTML, not drawn
in the PDF) and prints them in a strip under the slide, on the same page, in document order.
With --source the strip also carries the static slide's labels that the figure shortened or
reworded, so the page keeps the source's own words. Slides that need no strip get none.

Checks, per paper size (exit 1 on any FAIL):
  pages     the PDF has exactly one page per slide. A slide that overflows its page spills on
            a second page and fails here.
  labels    every piece of text inside a slide in the HTML is in the text of that slide's
            PDF page. Letter-spacing and case changes are ignored.
  on-page   every word on a page lies inside the page box.
  ink       every word on a page is drawn: the page is rendered and the word's box must show
            contrast. A label left at opacity 0, or covered, fails here.
  source    with --source: every label of the static slide is on the page as a whole phrase.
  size      WARN for a label smaller than --min-pt on paper.
  strip     INFO: which labels were moved into the strip under a slide, and why.

Needs Chrome (or Chromium, Edge) and poppler (pdftotext, pdftoppm, pdfinfo).
"""
import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from html.parser import HTMLParser

PAPERS = {'letter': (1056.0, 816.0), 'a4': (1122.52, 793.70)}   # landscape, CSS px (96 per inch)
SKIP = {'script', 'style', 'title', 'desc', 'metadata', 'defs', 'template', 'noscript', 'head'}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param',
        'source', 'track', 'wbr'}
HIDDEN_CLASS = re.compile(r'(^|\s)(sr-only|visually-hidden|screen-reader-text)(\s|$)')


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


def norm(s):
    """Fold a label for comparison: NFKC, lower case, no soft hyphens, straight quotes."""
    s = unicodedata.normalize('NFKC', s).replace('­', '')
    for a, b in (('’', "'"), ('‘', "'"), ('“', '"'), ('”', '"'),
                 ('–', '-'), ('—', '-'), ('−', '-'), (' ', ' ')):
        s = s.replace(a, b)
    return s.casefold()


def squash(s):
    """Letters and digits only: spacing, case and punctuation do not count."""
    return re.sub(r'[\W_]+', '', norm(s))


class SlideText(HTMLParser):
    """Collect the text pieces of every slide. A slide is an element that matches the
    selector: a class name ('.slide') or a tag name ('section'); nested matches stay inside
    their outermost slide."""

    def __init__(self, selector):
        super().__init__(convert_charrefs=True)
        self.cls = selector[1:] if selector.startswith('.') else None
        self.tag = None if self.cls else selector
        self.stack = []          # (tag, is_slide, skipped)
        self.slides = []         # list of lists of text pieces
        self.ends = []           # per slide: (line, column) of its end tag
        self.depth_slide = 0
        self.depth_skip = 0

    def is_slide(self, tag, attrs):
        if self.cls:
            return self.cls in (dict(attrs).get('class') or '').split()
        return tag == self.tag

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        a = dict(attrs)
        slide = self.depth_slide == 0 and self.is_slide(tag, attrs)
        skip = tag in SKIP or bool(HIDDEN_CLASS.search(a.get('class') or ''))
        self.stack.append((tag, slide, skip))
        if slide:
            self.depth_slide = 1
            self.slides.append([])
        if skip:
            self.depth_skip += 1

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for _, slide, skip in self.stack[i:]:
                    if slide:
                        self.depth_slide = 0
                        self.ends.append(self.getpos())
                    if skip:
                        self.depth_skip -= 1
                del self.stack[i:]
                return

    def handle_data(self, data):
        if self.depth_slide and not self.depth_skip:
            t = re.sub(r'\s+', ' ', data).strip()
            if t and re.search(r'\w', t):
                self.slides[-1].append(t)


def slide_labels(raw, selector):
    """(labels per slide, offset of each slide's end tag in raw)."""
    p = SlideText(selector)
    p.feed(raw)
    starts = [0]
    for line in raw.split('\n'):
        starts.append(starts[-1] + len(line) + 1)
    ends = [starts[ln - 1] + col for ln, col in p.ends]
    return p.slides, (ends if len(ends) == len(p.slides) else None)


def detect_selector(raw):
    if re.search(r'class="[^"]*\bslide\b', raw):
        return '.slide'
    return 'section'


def detect_stage(raw):
    """Fixed slide size from the deck's own rules, or None for a fluid deck."""
    css = ' '.join(re.findall(r'<style[^>]*>(.*?)</style>', raw, flags=re.S))
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    m = re.search(r'@page\s*\{[^}]*size\s*:\s*(\d{3,4})px\s+(\d{3,4})px', css)
    if m:
        return int(m.group(1)), int(m.group(2))
    for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
        if not re.search(r'(\.slide|\bsection|\.deck-stage|\.stage)\b', sel):
            continue
        w = re.search(r'(?<![-\w])width\s*:\s*(\d{3,4})px', body)
        h = re.search(r'(?<![-\w])height\s*:\s*(\d{3,4})px', body)
        if w and h:
            return int(w.group(1)), int(h.group(1))
    return None


BAND_PX = 10.67          # strip text: 8 pt on paper
BAND_LINE = 1.35


def band_height(texts, pw):
    """Paper px the strip needs: one block per text, wrapped at the page width."""
    per_line = (pw - 80) / (BAND_PX * 0.56)
    lines = sum(max(1, -(-len(t) // int(per_line))) for t in texts)
    return (lines + 1) * BAND_PX * BAND_LINE + 14


def fit_css(selector, paper, stage, bands):
    """bands: {slide index: paper px of strip under that slide}."""
    pw, ph = PAPERS[paper]
    css = ('@media print{@page{size:%.2fpx %.2fpx;margin:0}'
           'html,body{width:auto!important;height:auto!important;margin:0!important;'
           'padding:0!important;overflow:visible!important}'
           '*{-webkit-print-color-adjust:exact;print-color-adjust:exact}' % (pw, ph))

    def rule(sel, band):
        if stage:
            sw, sh = stage
            z = min(pw / sw, ph / sh)
            if (ph - sh * z) / 2 < band:            # no room under a centred slide: shrink it
                z = min(z, (ph - band) / sh)
                top = (ph - band - sh * z) / 2 / z
            else:
                top = (ph - sh * z) / 2 / z
            left = (pw - sw * z) / 2 / z
            # 0.5 px less than the page, so rounding never pushes a slide onto a second page
            out = ('%s{zoom:%.5f;width:%dpx!important;height:%.2fpx!important;'
                   'margin:%.2fpx 0 0 %.2fpx!important;box-sizing:border-box!important;'
                   'break-after:page;break-inside:avoid}' % (sel, z, sw, sh - 0.5 / z, top, left))
        else:
            z = 1.0
            out = ('%s{width:100vw!important;max-width:none!important;'
                   'height:calc(100vh - %.2fpx)!important;min-height:0!important;'
                   'margin:0!important;box-sizing:border-box!important;'
                   'break-after:page;break-inside:avoid}' % (sel, band + 0.5))
        if band:
            out += ('%s{position:relative!important;overflow:visible!important}'
                    '%s>.anim-print-band{display:block!important;position:absolute!important;'
                    'left:0;top:100%%;width:100%%;box-sizing:border-box;margin:0!important;'
                    'padding:%.2fpx %.2fpx!important;font:400 %.2fpx/%.2f system-ui,sans-serif!important;'
                    'color:#1a1a1a!important;background:#fff!important;'
                    'border-top:%.2fpx solid #888;letter-spacing:0!important;'
                    'text-transform:none!important;text-align:left!important;opacity:1!important;'
                    'visibility:visible!important;transform:none!important;animation:none!important}'
                    '%s>.anim-print-band p{margin:0!important;font:inherit!important;'
                    'color:inherit!important;max-width:none!important}'
                    '%s>.anim-print-band b{font-weight:700}'
                    % (sel, sel, 6 / z, 40 / z, BAND_PX / z, BAND_LINE, 1 / z, sel, sel))
        return out

    css += rule(selector, 0)
    for i, band in sorted(bands.items()):
        css += rule('%s[data-anim-print-page="%d"]' % (selector, i + 1), band)
    return '<style id="anim-slides-print-fit">' + css + '}</style>'


def band_texts(during, source, t_during, t_source):
    out = []
    for title, items in ((t_during, during), (t_source, source)):
        if items:
            out.append((title, '  '.join('%d. %s' % (n + 1, x) for n, x in enumerate(items))))
    return out


def build_page(raw, selector, paper, stage, ends, strips, titles):
    """The print copy: the fit rule, and a strip inside every slide that needs one.
    strips: {slide index: (labels shown only during the pass, source labels not on the page)}."""
    pw = PAPERS[paper][0]
    bands, page = {}, raw
    for i in sorted(strips, reverse=True):          # from the end, so offsets stay valid
        texts = band_texts(strips[i][0], strips[i][1], *titles)
        bands[i] = band_height(['%s: %s' % t for t in texts], pw)
        block = '<div class="anim-print-band">%s</div>' % ''.join(
            '<p><b>%s:</b> %s</p>' % (html.escape(t), html.escape(x)) for t, x in texts)
        page = page[:ends[i]] + block + page[ends[i]:]
    if bands:                                       # mark the slides that carry a strip
        marks = iter(sorted(bands))
        want, seen, out, pos = next(marks), -1, [], 0
        cls = selector[1:] if selector.startswith('.') else None
        pat = (r'<[a-zA-Z][^>]*\bclass="[^"]*\b%s\b[^"]*"[^>]*>' % re.escape(cls)) if cls \
            else r'<%s\b[^>]*>' % re.escape(selector)
        depth_end = 0
        for m in re.finditer(pat, page):
            if m.start() < depth_end:               # a nested match inside the current slide
                continue
            seen += 1
            depth_end = slide_end(page, m, selector)
            if seen == want:
                out.append(page[pos:m.end() - 1] + ' data-anim-print-page="%d">' % (seen + 1))
                pos = m.end()
                want = next(marks, None)
                if want is None:
                    break
        page = ''.join(out) + page[pos:]
    css = fit_css(selector, paper, stage, bands)
    return page.replace('</body>', css + '</body>', 1) if '</body>' in page else page + css


def slide_end(page, m, selector):
    """Offset where the slide opened by match m closes (same parser as slide_labels)."""
    p = SlideText(selector)
    p.feed(page[m.start():])
    if not p.ends:
        return len(page)
    ln, col = p.ends[0]
    return m.start() + sum(len(x) + 1 for x in page[m.start():].split('\n')[:ln - 1]) + col


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, timeout=180, **kw)


def print_pdf(chrome, page, out):
    cmd = [chrome, '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
           '--virtual-time-budget=4000', '--print-to-pdf=' + out, 'file://' + page]
    if os.environ.get('CI') or (hasattr(os, 'geteuid') and os.geteuid() == 0):
        cmd.insert(1, '--no-sandbox')
    run(cmd)
    return os.path.isfile(out) and os.path.getsize(out) > 0


def pdf_pages(pdf):
    """Per page: (width, height, [(word, x0, y0, x1, y1)]) in points."""
    x = run(['pdftotext', '-bbox', pdf, '-']).stdout.decode('utf-8', 'replace')
    pages = []
    for m in re.finditer(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', x, flags=re.S):
        words = [(html.unescape(w[4]), float(w[0]), float(w[1]), float(w[2]), float(w[3]))
                 for w in re.findall(r'<word xMin="([-\d.]+)" yMin="([-\d.]+)" xMax="([-\d.]+)" '
                                     r'yMax="([-\d.]+)">(.*?)</word>', m.group(3), flags=re.S)]
        pages.append((float(m.group(1)), float(m.group(2)), words))
    return pages


def page_text(pdf, n):
    """The page's text in three reading orders, each with whitespace removed."""
    out = []
    for flags in ([], ['-layout'], ['-raw']):
        t = run(['pdftotext'] + flags + ['-f', str(n), '-l', str(n), pdf, '-']).stdout
        out.append(squash(t.decode('utf-8', 'replace')))
    return out


def read_pgm(path):
    with open(path, 'rb') as f:
        data = f.read()
    m = re.match(rb'P5\s+(?:#[^\n]*\n\s*)*(\d+)\s+(\d+)\s+(\d+)\s', data)
    w, h = int(m.group(1)), int(m.group(2))
    return w, h, data[m.end():]


def ink(pix, w, h, box, scale):
    """Contrast range of the pixels inside a word box (points -> pixels)."""
    x0, y0 = max(0, int(box[0] * scale)), max(0, int(box[1] * scale))
    x1, y1 = min(w, int(box[2] * scale) + 1), min(h, int(box[3] * scale) + 1)
    lo, hi = 255, 0
    for y in range(y0, y1):
        row = pix[y * w + x0:y * w + x1]
        if row:
            lo, hi = min(lo, min(row)), max(hi, max(row))
    return hi - lo


def on_page(label, texts, exact=False):
    q = squash(label)
    if not q or any(q in t for t in texts):
        return True
    if exact:
        return False
    # every word is there, in another reading order (text set in columns, or on a curve)
    return all(any(squash(w) in t for t in texts) for w in label.split())


def check_pdf(pdf, labels, work, min_pt, source=None):
    """Returns (fails, warns, undrawn, unsourced, stats). undrawn and unsourced are
    {slide index: [labels]}: in the HTML but not drawn, and in the static deck but not here."""
    fails, warns, undrawn, unsourced = [], [], {}, {}
    pages = pdf_pages(pdf)
    if len(pages) != len(labels):
        fails.append('pages: %d slides in the deck, %d pages in the PDF (a slide spills over its '
                     'page, or a slide is hidden in print; try --stage or --slides)'
                     % (len(labels), len(pages)))
        return fails, warns, undrawn, unsourced, (len(pages), 0, 0)
    n_labels = n_words = 0
    dpi = 144
    run(['pdftoppm', '-gray', '-r', str(dpi), pdf, os.path.join(work, 'pg')])
    pgms = sorted(f for f in os.listdir(work) if f.startswith('pg') and f.endswith('.pgm'))
    for i, (pw, ph, words) in enumerate(pages):
        texts = page_text(pdf, i + 1)
        w, h, pix = read_pgm(os.path.join(work, pgms[i])) if i < len(pgms) else (0, 0, b'')
        small, drawn, blank = [], set(), []
        for word, x0, y0, x1, y1 in words:
            if not re.search(r'\w', word):
                continue
            n_words += 1
            if x0 < -0.5 or y0 < -0.5 or x1 > pw + 0.5 or y1 > ph + 0.5:
                fails.append('on-page: slide %d, "%s" runs off the page' % (i + 1, word))
            elif pix and ink(pix, w, h, (x0, y0, x1, y1), dpi / 72.0) < 24:
                blank.append(word)
                continue
            drawn.add(squash(word))
            if y1 - y0 < min_pt:
                small.append((y1 - y0, word))
        # a word without ink is a fault unless the same word is drawn elsewhere on the page
        lost = [b for b in blank if squash(b) not in drawn]
        for b in lost:
            fails.append('ink: slide %d, "%s" is in the PDF text but not drawn '
                         '(hidden, transparent or covered)' % (i + 1, b))
        lost = set(squash(b) for b in lost)
        for lab in labels[i]:
            n_labels += 1
            toks = [squash(x) for x in lab.split() if squash(x)]
            if not on_page(lab, texts) or (toks and all(t in lost for t in toks)):
                undrawn.setdefault(i, []).append(lab)
                fails.append('labels: slide %d, "%s" is not on page %d' % (i + 1, lab, i + 1))
        if small:
            small.sort()
            warns.append('size: slide %d, %d words under %g pt on paper; smallest %.1f pt ("%s")'
                         % (i + 1, len(small), min_pt, small[0][0], small[0][1]))
        if source:
            for lab in source[i]:
                if not on_page(lab, texts, exact=True):
                    unsourced.setdefault(i, []).append(lab)
                    fails.append('source: slide %d, the static slide says "%s"; page %d does not'
                                 % (i + 1, lab, i + 1))
    return fails, warns, undrawn, unsourced, (len(pages), n_labels, n_words)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('deck')
    ap.add_argument('--paper', choices=['letter', 'a4', 'both'], default='both')
    ap.add_argument('--out')
    ap.add_argument('--stage')
    ap.add_argument('--slides')
    ap.add_argument('--source')
    ap.add_argument('--min-pt', type=float, default=6.0)
    ap.add_argument('--chrome')
    ap.add_argument('--during-title', default='Shown during the animation')
    ap.add_argument('--source-title', default='Source text')
    a = ap.parse_args()

    chrome = find_chrome(a.chrome)
    if not chrome:
        sys.exit('export_pdf: no Chrome, Chromium or Edge found; set CHROME or pass --chrome')
    missing = [t for t in ('pdftotext', 'pdftoppm') if not shutil.which(t)]
    if missing:
        sys.exit('export_pdf: %s not found; install poppler (brew install poppler, '
                 'apt-get install poppler-utils)' % ', '.join(missing))

    deck = os.path.abspath(a.deck)
    with open(deck, encoding='utf-8') as f:
        raw = f.read()
    selector = a.slides or detect_selector(raw)
    if not re.fullmatch(r'\.?[A-Za-z][\w-]*', selector):
        sys.exit('export_pdf: --slides takes one class (.slide) or one tag (section)')
    if a.stage and a.stage != 'fluid':
        m = re.fullmatch(r'(\d+)x(\d+)', a.stage)
        if not m:
            sys.exit('export_pdf: --stage takes WxH in px (1920x1080) or fluid')
        stage = (int(m.group(1)), int(m.group(2)))
    else:
        stage = None if a.stage == 'fluid' else detect_stage(raw)
    labels, ends = slide_labels(raw, selector)
    if not labels:
        sys.exit('export_pdf: no slide found with selector %s; pass --slides' % selector)
    source = None
    if a.source:
        with open(a.source, encoding='utf-8') as f:
            sraw = f.read()
        source = slide_labels(sraw, a.slides or detect_selector(sraw))[0]
        if len(source) != len(labels):
            sys.exit('export_pdf: --source has %d slides, the deck has %d; the two decks must '
                     'have the same slides in the same order' % (len(source), len(labels)))

    out_dir = os.path.abspath(a.out or os.path.dirname(deck))
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(deck))[0]
    print('export_pdf: %s, %d slides (%s), stage %s' % (
        os.path.basename(deck), len(labels), selector,
        '%dx%d' % stage if stage else 'fluid'))
    titles = (a.during_title, a.source_title)

    def export(paper, pdf, strips):
        page = build_page(raw, selector, paper, stage, ends, strips, titles)
        # the copy sits next to the deck, so relative images and fonts still load
        fd, tmp = tempfile.mkstemp(prefix='.' + stem + '-print-', suffix='.html',
                                   dir=os.path.dirname(deck))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(page)
            if os.path.exists(pdf):
                os.remove(pdf)
            if not print_pdf(chrome, tmp, pdf):
                return None
        finally:
            os.remove(tmp)
        with tempfile.TemporaryDirectory() as work:
            return check_pdf(pdf, labels, work, a.min_pt, source)

    bad = False
    for paper in (['letter', 'a4'] if a.paper == 'both' else [a.paper]):
        pdf = os.path.join(out_dir, '%s-%s.pdf' % (stem, paper))
        res = export(paper, pdf, {})
        strips = {}
        if res and ends and (res[2] or res[3]):
            # labels the resting frame cannot show, and source words the figure does not
            # carry: print them in a strip under their slide and export again
            strips = {i: (res[2].get(i, []), res[3].get(i, []))
                      for i in set(res[2]) | set(res[3])}
            res = export(paper, pdf, strips)
        if not res:
            print('  FAIL  %s: Chrome wrote no PDF' % paper)
            bad = True
            continue
        fails, warns, _, _, (np, nl, nw) = res
        print('  %s  %s: %s, %d pages for %d slides, %d of %d labels on their page, %d words drawn'
              % ('FAIL' if fails else 'OK  ', paper, pdf, np, len(labels),
                 nl - sum(f.startswith('labels') for f in fails), nl, nw))
        infos = []
        for i in sorted(strips):
            during, src = strips[i]
            if during:
                infos.append('strip: slide %d, %d labels are on screen only during the animation; '
                             'printed under the slide: %s'
                             % (i + 1, len(during), '; '.join('"%s"' % x for x in during)))
            if src:
                infos.append('strip: slide %d, %d source labels are not in the figure in the '
                             "source's words; printed under the slide: %s"
                             % (i + 1, len(src), '; '.join('"%s"' % x for x in src)))
        for level, items in (('FAIL', fails), ('WARN', warns), ('INFO', infos)):
            for it in items:
                print('    %s  %s' % (level, it))
        bad = bad or bool(fails)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
