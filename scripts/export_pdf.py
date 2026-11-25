#!/usr/bin/env python3
"""Export a deck to PDF, one slide per Letter or A4 landscape page, and prove that every
label in the deck is on its page. With --install the deck itself carries the print rule, so
the browser's own Print (Ctrl/Cmd+P) gives the same pages on either paper.

Usage:
  export_pdf.py DECK.html [--paper letter|a4|both] [--out DIR] [--install]
                [--stage WxH|fluid] [--slides SELECTOR] [--source STATIC.html]
                [--min-pt N] [--chrome PATH] [--during-title TEXT] [--source-title TEXT]

  --paper    paper size, landscape (default: both; writes DECK-letter.pdf and DECK-a4.pdf)
  --out      folder for the PDFs (default: next to the deck)
  --install  after every paper passed, write the print rule (and the strips, see below) into
             the deck, between <!-- anim-slides:print-fit:start --> and :end. The rule names no
             paper size: it scales the slide to whatever page the print dialog offers. A second
             run replaces the first. Without --install the deck file is not changed
  --stage    the deck's fixed slide size in px, e.g. 1920x1080, or 'fluid' for a deck whose
             slides follow the viewport. Default: read from the deck's own print rules
             (@page size, or a px width and height on the slide rule); fluid when none is found
  --slides   CSS selector of one slide (default: '.slide' when the deck uses that class, else
             'section')
  --source   the deck before figures were added (the static deck). Every label of a static
             slide must be on the same page of this deck's PDF, in the source's words
  --min-pt   warn when a label is smaller than this on paper (default 6 pt)

How it prints. A copy of the deck gets one print rule: landscape, no page margin, and a scale
computed in CSS from the page itself (a fixed stage is zoomed to fit and centred; a fluid
slide takes the page). Animations show their resting frame because of each fragment's print
guard (integrate_fragment.py). The export only adds the paper size on top of that rule.

Strips. A resting frame cannot show what was on screen only during the pass (step captions
that cross-fade, a state label that changes). The script finds those labels (in the HTML, not
drawn in the PDF) and prints them in a strip under the slide, on the same page, in document
order. With --source the strip also carries the static slide's labels that the figure
shortened or reworded. Slides that need no strip get none.

Presenter notes are not labels. <aside class="notes">, .notes, .speaker-notes,
.presenter-notes, .presenter-only and [data-presenter-only] are hidden in print, never go
into a strip, and fail the export if their text shows on a page.

Checks, per paper size (exit 1 on any FAIL):
  pages     the PDF has exactly one page per slide. A slide that overflows its page spills on
            a second page and fails here.
  labels    every piece of text inside a slide in the HTML is in the text of that slide's
            PDF page, as often as the slide has it. Letter-spacing and case are ignored.
  table     every cell of a <table> is drawn in its own cell: the values of one row sit left
            to right in column order, rows sit top to bottom, and columns do not cross. A
            value that repeats is matched once per cell, across all tables of the slide, so a
            "12" in one table cannot stand in for a missing "12" in another.
  on-page   every word on a page lies inside the page box.
  ink       every word on a page is drawn: the page is rendered and the word's box must show
            contrast. A label left at opacity 0, or covered, fails here.
  notes     no presenter note is on a page: a note fails when its text is on the page more
            often than the slide's own labels say it (a note that repeats the title passes).
  source    with --source: every label of the static slide is on the page as a whole phrase.
  size      WARN for a label smaller than --min-pt on paper.
  strip     INFO: which labels were moved into the strip under a slide, and why.

An existing PDF is replaced only by a PDF that passed. A failing export is kept next to it as
DECK-PAPER.rejected.pdf, and the old file stays as it was.

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
from collections import Counter
from html.parser import HTMLParser

PAPERS = {'letter': ('11in 8.5in', 1056.0), 'a4': ('297mm 210mm', 1122.52)}   # landscape; width in CSS px
SKIP = {'script', 'style', 'title', 'desc', 'metadata', 'defs', 'template', 'noscript', 'head'}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param',
        'source', 'track', 'wbr'}
HIDDEN_CLASS = {'sr-only', 'visually-hidden', 'screen-reader-text', 'anim-print-band'}
NOTE_CLASS = {'notes', 'speaker-notes', 'presenter-notes', 'presenter-only'}
NOTE_CSS = ('aside.notes,.notes,.speaker-notes,.presenter-notes,.presenter-only,'
            '[data-presenter-only]')
START, END = '<!-- anim-slides:print-fit:start -->', '<!-- anim-slides:print-fit:end -->'
BAND_PX = 10.67          # strip text: 8 pt on paper
BAND_LINE = 1.35


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
    """Fold a label for comparison: NFKC, lower case, no soft hyphens."""
    return unicodedata.normalize('NFKC', s).replace('­', '').casefold()


def squash(s):
    """Letters and digits only: spacing, case and punctuation do not count."""
    return re.sub(r'[\W_]+', '', norm(s))


# ---------------------------------------------------------------- reading the deck

class Slide(object):
    def __init__(self):
        self.labels = []     # text pieces, document order (table cells included)
        self.loose = []      # the pieces that are not in a table
        self.tables = []     # [{'rows': [[cell text, ...], ...], 'spans': bool}]
        self.notes = []      # presenter notes: never printed
        self.end = None      # (line, column) of the slide's end tag


class SlideText(HTMLParser):
    """Collect the text of every slide. A slide is an element that matches the selector: a
    class name ('.slide') or a tag name ('section'); nested matches stay inside their
    outermost slide."""

    def __init__(self, selector):
        super().__init__(convert_charrefs=True)
        self.cls = selector[1:] if selector.startswith('.') else None
        self.tag = None if self.cls else selector
        self.stack = []          # (tag, kind) with kind in slide/skip/note/table/tr/cell/None
        self.slides = []
        self.in_slide = self.skip = self.note = 0
        self.table = self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        a = dict(attrs)
        classes = set((a.get('class') or '').split())
        kind = None
        if not self.in_slide and (self.cls in classes if self.cls else tag == self.tag):
            kind = 'slide'
            self.in_slide = 1
            self.slides.append(Slide())
        elif tag in SKIP or classes & HIDDEN_CLASS:
            kind = 'skip'
            self.skip += 1
        elif classes & NOTE_CLASS or 'data-presenter-only' in a:
            kind = 'note'
            self.note += 1
        elif self.in_slide and tag == 'table' and self.table is None:
            kind = 'table'
            self.table = {'rows': [], 'spans': False}
        elif self.table is not None and tag == 'tr':
            kind = 'tr'
            self.table['rows'].append([])
        elif self.table is not None and tag in ('td', 'th') and self.cell is None \
                and self.table['rows']:
            kind = 'cell'
            self.cell = []
            if a.get('colspan', '1') != '1' or a.get('rowspan', '1') != '1':
                self.table['spans'] = True
        self.stack.append((tag, kind))

    def handle_startendtag(self, tag, attrs):
        pass

    def close(self, kind):
        s = self.slides[-1] if self.slides else None
        if kind == 'slide':
            self.in_slide = 0
            s.end = self.getpos()
        elif kind == 'skip':
            self.skip -= 1
        elif kind == 'note':
            self.note -= 1
        elif kind == 'cell':
            self.table['rows'][-1].append(' '.join(self.cell))
            self.cell = None
        elif kind == 'table':
            if any(any(c for c in r) for r in self.table['rows']):
                s.tables.append(self.table)
            self.table = None

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for _, kind in reversed(self.stack[i:]):
                    self.close(kind)
                del self.stack[i:]
                return

    def handle_data(self, data):
        if not self.in_slide or self.skip:
            return
        t = re.sub(r'\s+', ' ', data).strip()
        if not t or not re.search(r'\w', t):
            return
        s = self.slides[-1]
        if self.note:
            s.notes.append(t)
            return
        s.labels.append(t)
        if self.cell is not None:
            self.cell.append(t)
        elif self.table is None:
            s.loose.append(t)


def read_slides(raw, selector):
    """(slides, offset of each slide's end tag in raw)."""
    p = SlideText(selector)
    p.feed(raw)
    starts = [0]
    for line in raw.split('\n'):
        starts.append(starts[-1] + len(line) + 1)
    ends = [starts[s.end[0] - 1] + s.end[1] if s.end else None for s in p.slides]
    return p.slides, (ends if all(e is not None for e in ends) else None)


def slide_labels(raw, selector):
    """Label pieces per slide (kept for callers that need only the text)."""
    slides, ends = read_slides(raw, selector)
    return [s.labels for s in slides], ends


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


def uninstall(raw):
    """The deck without an earlier --install (rule, strips, slide marks)."""
    raw = re.sub(re.escape(START) + r'.*?' + re.escape(END) + r'\n?', '', raw, flags=re.S)
    raw = re.sub(r'<div class="anim-print-band">.*?</div>', '', raw, flags=re.S)
    return re.sub(r' data-anim-print-page="\d+"', '', raw)


# ---------------------------------------------------------------- the print rule

def band_height(texts):
    """Paper px the strip needs, wrapped at the narrower paper (Letter)."""
    per_line = int((PAPERS['letter'][1] - 80) / (BAND_PX * 0.56))
    lines = sum(max(1, -(-len(t) // per_line)) for t in texts)
    return (lines + 1) * BAND_PX * BAND_LINE + 14


def fit_css(selector, stage, bands):
    """The print rule. It names no paper: the scale comes from the page (100vw, 100vh), so
    the same rule fits Letter and A4. bands: {slide index: paper px of strip under it}."""
    band_sel = '%s>.anim-print-band' % selector
    css = ('.anim-print-band{display:none}'
           '@media print{@page{size:landscape;margin:0}'
           'html,body{width:auto!important;height:auto!important;margin:0!important;'
           'padding:0!important;overflow:visible!important}'
           '*{-webkit-print-color-adjust:exact;print-color-adjust:exact}'
           '%s{display:none!important}' % NOTE_CSS)
    if stage:
        sw, sh = stage
        # tan(atan2(a, b)) is a/b as a plain number: the zoom that fits the stage on the page.
        # 1 px less than the stage, so rounding never pushes a slide onto a second page.
        css += ('%s{--anim-print-band:0px;'
                '--anim-print-s:min(tan(atan2(100vw,%dpx)),tan(atan2(calc(100vh - var(--anim-print-band)),%dpx)));'
                'zoom:var(--anim-print-s);width:%dpx!important;height:%dpx!important;'
                'margin:calc((100vh - var(--anim-print-band))/var(--anim-print-s)/2 - %.1fpx) 0 0 '
                'calc(100vw/var(--anim-print-s)/2 - %.1fpx)!important;'
                'box-sizing:border-box!important;break-after:page;break-inside:avoid}'
                % (selector, sw, sh, sw, sh - 1, sh / 2.0, sw / 2.0))
        unit = '/var(--anim-print-s)'
    else:
        css += ('%s{--anim-print-band:0px;width:100vw!important;max-width:none!important;'
                'height:calc(100vh - var(--anim-print-band) - 0.5px)!important;'
                'min-height:0!important;margin:0!important;box-sizing:border-box!important;'
                'break-after:page;break-inside:avoid}' % selector)
        unit = ''
    if bands:
        css += ('%s[data-anim-print-page]{position:relative!important;overflow:visible!important}'
                '%s{display:block!important;position:absolute!important;left:0;top:100%%;'
                'width:100%%;box-sizing:border-box;margin:0!important;'
                'padding:calc(6px%s) calc(40px%s)!important;'
                'font:400 calc(%.2fpx%s)/%.2f system-ui,sans-serif!important;'
                'color:#1a1a1a!important;background:#fff!important;'
                'border-top:calc(1px%s) solid #888;letter-spacing:0!important;'
                'text-transform:none!important;text-align:left!important;opacity:1!important;'
                'visibility:visible!important;transform:none!important;animation:none!important}'
                '%s p{margin:0!important;font:inherit!important;color:inherit!important;'
                'max-width:none!important}%s b{font-weight:700}'
                % (selector, band_sel, unit, unit, BAND_PX, unit, BAND_LINE, unit,
                   band_sel, band_sel))
        for i, band in sorted(bands.items()):
            css += '%s[data-anim-print-page="%d"]{--anim-print-band:%.1fpx}' % (selector, i + 1, band)
    return START + '\n<style>' + css + '}</style>\n' + END + '\n'


def band_texts(during, source, t_during, t_source):
    out = []
    for title, items in ((t_during, during), (t_source, source)):
        if items:
            out.append((title, '  '.join('%d. %s' % (n + 1, x) for n, x in enumerate(items))))
    return out


def build_page(raw, selector, stage, ends, strips, titles):
    """The deck with the print rule and a strip inside every slide that needs one.
    strips: {slide index: (labels shown only during the pass, source labels not on the page)}."""
    bands, page = {}, raw
    for i in sorted(strips, reverse=True):          # from the end, so offsets stay valid
        texts = band_texts(strips[i][0], strips[i][1], *titles)
        bands[i] = band_height(['%s: %s' % t for t in texts])
        block = '<div class="anim-print-band">%s</div>' % ''.join(
            '<p><b>%s:</b> %s</p>' % (html.escape(t), html.escape(x)) for t, x in texts)
        page = page[:ends[i]] + block + page[ends[i]:]
    if bands:                                       # mark the slides that carry a strip
        cls = selector[1:] if selector.startswith('.') else None
        pat = (r'<[a-zA-Z][^>]*\bclass="[^"]*\b%s\b[^"]*"[^>]*>' % re.escape(cls)) if cls \
            else r'<%s\b[^>]*>' % re.escape(selector)
        out, pos, seen, inside = [], 0, -1, 0
        for m in re.finditer(pat, page):
            if m.start() < inside:                  # a nested match inside the current slide
                continue
            seen += 1
            inside = slide_end(page, m, selector)
            if seen in bands:
                out.append(page[pos:m.end() - 1] + ' data-anim-print-page="%d">' % (seen + 1))
                pos = m.end()
        page = ''.join(out) + page[pos:]
    css = fit_css(selector, stage, bands)
    return page.replace('</body>', css + '</body>', 1) if '</body>' in page else page + css


def slide_end(page, m, selector):
    """Offset where the slide opened by match m closes."""
    slides, ends = read_slides(page[m.start():], selector)
    return m.start() + ends[0] if ends else len(page)


# ---------------------------------------------------------------- reading the PDF

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
    """The page's text in three reading orders, each squashed."""
    out = []
    for flags in ([], ['-layout'], ['-raw']):
        t = run(['pdftotext'] + flags + ['-f', str(n), '-l', str(n), pdf, '-']).stdout
        out.append(squash(t.decode('utf-8', 'replace')))
    return out


def read_pgm(path):
    with open(path, 'rb') as f:
        data = f.read()
    m = re.match(rb'P5\s+(?:#[^\n]*\n\s*)*(\d+)\s+(\d+)\s+(\d+)\s', data)
    return int(m.group(1)), int(m.group(2)), data[m.end():]


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


def occurrences(label, words):
    """Where the label is drawn: runs of whole words whose letters spell it. words are the
    drawn words of a page, [(squashed text, x0, y0, x1, y1)]. Returns [(first, last, cx, cy)]."""
    q = squash(label)
    if not q:
        return []
    stream, start_at, end_at = '', {}, {}
    for i, w in enumerate(words):
        start_at[len(stream)] = i
        stream += w[0]
        end_at[len(stream)] = i
    out, pos = [], stream.find(q)
    while pos >= 0:
        if pos in start_at and pos + len(q) in end_at:
            i0, i1 = start_at[pos], end_at[pos + len(q)]
            box = words[i0:i1 + 1]
            x0, y0 = min(b[1] for b in box), min(b[2] for b in box)
            x1, y1 = max(b[3] for b in box), max(b[4] for b in box)
            out.append((i0, i1, (x0 + x1) / 2, (y0 + y1) / 2))
        pos = stream.find(q, pos + 1)
    return out


def place_tables(tables, words):
    """Match every cell of every table on a page to its own drawn text, all tables at once:
    drawn words fill one cell only, so two tables that both say "12" need two drawn "12"s.
    Returns (bad, used): bad is None when all cells are placed, else (table, row, column,
    text) of the first cell that has no place, or 'unknown' when the search was cut short;
    used is the set of word indices the cells took (empty unless all were placed)."""
    cells = [(n, r, c, t) for n, table in enumerate(tables) for r, row in enumerate(table['rows'])
             for c, t in enumerate(row) if squash(t)]
    cands = [occurrences(t, words) for _, _, _, t in cells]
    best = [0]
    budget = [40000 * max(1, len(tables))]

    def fits(k, o, placed):
        n, r, c, _ = cells[k]
        strict = not tables[n]['spans']
        for j, p in placed:
            n2, r2, c2, _ = cells[j]
            if not (p[1] < o[0] or o[1] < p[0]):
                return False                         # the same words cannot fill two cells
            if n2 != n:
                continue                             # tables stand anywhere relative to each other
            if r2 < r and not p[3] < o[3]:
                return False                         # rows run top to bottom
            if r2 == r and c2 < c and not p[2] < o[2]:
                return False                         # a row runs left to right
            if strict and c2 != c and (c2 < c) != (p[2] < o[2]):
                return False                         # columns do not cross
        return True

    found = []

    def go(k, placed):
        best[0] = max(best[0], k)
        if k == len(cells):
            found.extend(placed)
            return True
        for o in cands[k]:
            budget[0] -= 1
            if budget[0] < 0:
                return False
            if fits(k, o, placed) and go(k + 1, placed + [(k, o)]):
                return True
        return False

    if go(0, []):
        return None, set(i for _, o in found for i in range(o[0], o[1] + 1))
    if budget[0] < 0:
        return 'unknown', set()
    return cells[best[0]], set()


def place_table(table, words):
    """One table alone: None, 'unknown', or (row, column, text) of the first cell without a place."""
    bad = place_tables([table], words)[0]
    return bad[1:] if isinstance(bad, tuple) else bad


def printed_more_often(text, labels, texts):
    """True when the page shows text more often than the slide's labels account for: a note
    that repeats a visible title is on the page once, through the title, and that is fine."""
    q = squash(text)
    return max(t.count(q) for t in texts) > squash(' '.join(labels)).count(q)


def check_pdf(pdf, slides, work, min_pt, source=None):
    """Returns (fails, warns, undrawn, unsourced, stats). undrawn and unsourced are
    {slide index: [labels]}: in the HTML but not drawn, and in the static deck but not here."""
    fails, warns, undrawn, unsourced = [], [], {}, {}
    pages = pdf_pages(pdf)
    if len(pages) != len(slides):
        fails.append('pages: %d slides in the deck, %d pages in the PDF (a slide spills over its '
                     'page, or a slide is hidden in print; try --stage or --slides)'
                     % (len(slides), len(pages)))
        return fails, warns, undrawn, unsourced, (len(pages), 0, 0)
    n_labels = n_words = 0
    dpi = 144
    run(['pdftoppm', '-gray', '-r', str(dpi), pdf, os.path.join(work, 'pg')])
    pgms = sorted(f for f in os.listdir(work) if f.startswith('pg') and f.endswith('.pgm'))
    for i, (pw, ph, words) in enumerate(pages):
        slide = slides[i]
        texts = page_text(pdf, i + 1)
        w, h, pix = read_pgm(os.path.join(work, pgms[i])) if i < len(pgms) else (0, 0, b'')
        small, drawn, blank = [], [], []
        for word, x0, y0, x1, y1 in words:
            if not re.search(r'\w', word):
                continue
            n_words += 1
            if x0 < -0.5 or y0 < -0.5 or x1 > pw + 0.5 or y1 > ph + 0.5:
                fails.append('on-page: slide %d, "%s" runs off the page' % (i + 1, word))
            elif pix and ink(pix, w, h, (x0, y0, x1, y1), dpi / 72.0) < 24:
                blank.append(word)
                continue
            drawn.append((squash(word), x0, y0, x1, y1))
            if y1 - y0 < min_pt:
                small.append((y1 - y0, word))
        # a word without ink is a fault unless the same word is drawn elsewhere on the page
        seen = set(d[0] for d in drawn)
        lost = [b for b in blank if squash(b) not in seen]
        for b in lost:
            fails.append('ink: slide %d, "%s" is in the PDF text but not drawn '
                         '(hidden, transparent or covered)' % (i + 1, b))
        lost = set(squash(b) for b in lost)

        def miss(lab):
            undrawn.setdefault(i, []).append(lab)
            fails.append('labels: slide %d, "%s" is not on page %d' % (i + 1, lab, i + 1))

        n_labels += len(slide.labels)
        for lab in slide.labels:
            toks = [squash(x) for x in lab.split() if squash(x)]
            if not on_page(lab, texts) or (toks and all(t in lost for t in toks)):
                miss(lab)
        # every table cell takes its own drawn words, across all tables of the slide
        bad, used = place_tables(slide.tables, drawn)
        if bad == 'unknown':
            warns.append('table: slide %d, the tables are too large to verify cell by cell' % (i + 1))
        elif bad:
            fails.append('table: slide %d, table %d, row %d column %d: "%s" is not drawn in '
                         'its cell' % (i + 1, bad[0] + 1, bad[1] + 1, bad[2] + 1, bad[3]))
        # a label the slide has several times, or that a table cell also says, must be drawn
        # that often outside the words the table cells took
        done = set(squash(x) for x in undrawn.get(i, []))
        counts = Counter(squash(x) for x in slide.loose)
        in_cells = set(squash(c) for table in slide.tables for row in table['rows'] for c in row)
        for lab in dict.fromkeys(slide.loose):
            q = squash(lab)
            if (counts[q] > 1 or q in in_cells) and q not in done:
                free = [o for o in occurrences(lab, drawn)
                        if not any(k in used for k in range(o[0], o[1] + 1))]
                for _ in range(counts[q] - len(free)):
                    miss(lab)
        for note in slide.notes:
            if on_page(note, texts, exact=True) and len(squash(note)) > 3 \
                    and printed_more_often(note, slide.labels, texts):
                fails.append('notes: slide %d, the presenter note "%s" is on page %d'
                             % (i + 1, note, i + 1))
        if small:
            small.sort()
            warns.append('size: slide %d, %d words under %g pt on paper; smallest %.1f pt ("%s")'
                         % (i + 1, len(small), min_pt, small[0][0], small[0][1]))
        if source:
            for lab in source[i].labels:
                if not on_page(lab, texts, exact=True):
                    unsourced.setdefault(i, []).append(lab)
                    fails.append('source: slide %d, the static slide says "%s"; page %d does not'
                                 % (i + 1, lab, i + 1))
    return fails, warns, undrawn, unsourced, (len(pages), n_labels, n_words)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('deck')
    ap.add_argument('--paper', choices=['letter', 'a4', 'both'], default='both')
    ap.add_argument('--out')
    ap.add_argument('--install', action='store_true')
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
        raw = uninstall(f.read())
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
    slides, ends = read_slides(raw, selector)
    if not slides:
        sys.exit('export_pdf: no slide found with selector %s; pass --slides' % selector)
    source = None
    if a.source:
        with open(a.source, encoding='utf-8') as f:
            sraw = uninstall(f.read())
        source = read_slides(sraw, a.slides or detect_selector(sraw))[0]
        if len(source) != len(slides):
            sys.exit('export_pdf: --source has %d slides, the deck has %d; the two decks must '
                     'have the same slides in the same order' % (len(source), len(slides)))

    out_dir = os.path.abspath(a.out or os.path.dirname(deck))
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(deck))[0]
    n_notes = sum(len(s.notes) for s in slides)
    print('export_pdf: %s, %d slides (%s), stage %s%s' % (
        os.path.basename(deck), len(slides), selector,
        '%dx%d' % stage if stage else 'fluid',
        ', %d presenter notes left out' % n_notes if n_notes else ''))
    titles = (a.during_title, a.source_title)

    def export(paper, pdf, strips):
        """Print the deck with its print rule on this paper; returns (page html, check)."""
        page = build_page(raw, selector, stage, ends, strips, titles)
        sized = page.replace(END, '<style>@page{size:%s;margin:0}</style>%s' % (PAPERS[paper][0], END), 1)
        # the copy sits next to the deck, so relative images and fonts still load
        fd, tmp = tempfile.mkstemp(prefix='.' + stem + '-print-', suffix='.html',
                                   dir=os.path.dirname(deck))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(sized)
            if not print_pdf(chrome, tmp, pdf):
                return page, None
        finally:
            os.remove(tmp)
        with tempfile.TemporaryDirectory() as work:
            return page, check_pdf(pdf, slides, work, a.min_pt, source)

    bad, installed = False, None
    for paper in (['letter', 'a4'] if a.paper == 'both' else [a.paper]):
        final = os.path.join(out_dir, '%s-%s.pdf' % (stem, paper))
        rejected = os.path.join(out_dir, '%s-%s.rejected.pdf' % (stem, paper))
        fd, draft = tempfile.mkstemp(prefix='.' + stem + '-' + paper + '-', suffix='.pdf', dir=out_dir)
        os.close(fd)
        page, res = export(paper, draft, {})
        strips = {}
        if res and ends and (res[2] or res[3]):
            # labels the resting frame cannot show, and source words the figure does not
            # carry: print them in a strip under their slide and export again
            strips = {i: (res[2].get(i, []), res[3].get(i, []))
                      for i in set(res[2]) | set(res[3])}
            page, res = export(paper, draft, strips)
        if not res:
            print('  FAIL  %s: Chrome wrote no PDF' % paper)
            if os.path.exists(draft):
                os.remove(draft)
            bad = True
            continue
        fails, warns, _, _, (np, nl, nw) = res
        # an existing PDF gives way only to one that passed
        if fails:
            os.replace(draft, rejected)
            where = '%s (not accepted%s)' % (rejected, '; %s is unchanged' % final
                                             if os.path.exists(final) else '')
        else:
            os.chmod(draft, 0o644)          # mkstemp made it private to the user
            os.replace(draft, final)
            if os.path.exists(rejected):
                os.remove(rejected)
            where = final
            installed = installed or page
        print('  %s  %s: %s, %d pages for %d slides, %d of %d labels on their page, %d words drawn'
              % ('FAIL' if fails else 'OK  ', paper, where, np, len(slides),
                 nl - len(set(f for f in fails if f.startswith(('labels', 'table')))), nl, nw))
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
    if a.install:
        if bad or not installed:
            print('  deck not changed: --install writes the print rule only after every paper passed')
        else:
            with open(deck, 'w', encoding='utf-8') as f:
                f.write(installed)
            print('  installed the print rule in %s: the browser\'s Print now gives these pages '
                  'on Letter and A4 (landscape, no margins)' % deck)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
