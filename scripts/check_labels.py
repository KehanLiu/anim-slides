#!/usr/bin/env python3
"""Every label of the source slide is still on the animated slide, word for word.

Usage:
  check_labels.py BEFORE.html AFTER.html --slide N [--selector CSS-CLASS] [--allow FILE]

Reads slide N of both decks (the Nth element with class "slide", else the Nth <section>) and
compares their text: each text run of the source slide (a heading, a table heading or cell, a
list item, a sentence, a number with its unit) must appear on the animated slide with the same
words, in SVG <text> or in HTML. Spacing, case, line breaks and punctuation are
ignored, so a label wrapped over two <tspan> lines still matches; a shortened or reworded
label, a dropped table heading and a changed unit ("hours" to "h") do not.

Prints OK or one FAIL line per missing run with the closest text found; exit 1 on any FAIL.
--allow FILE lists runs that may be dropped on purpose, one per line (say why in the hand-over).
Standard library only.
"""
import argparse
import difflib
import re
import sys
import unicodedata
from html.parser import HTMLParser

SKIP = {'script', 'style', 'template', 'title', 'desc', 'metadata', 'defs'}
INLINE = {'tspan', 'a', 'em', 'i', 'b', 'strong', 'u', 'sub', 'sup', 'wbr', 'abbr', 'mark'}   # stay inside a run
VOID = {'br', 'img', 'hr', 'input', 'meta', 'link', 'source', 'path', 'rect', 'circle', 'line', 'use', 'stop'}


def squash(s):
    """Whole words in order, as one string with single spaces: case, spacing and punctuation ignored."""
    s = unicodedata.normalize('NFKC', s).casefold().replace('\u00ad', '')
    return ' ' + ' '.join(re.findall(r'[^\W_]+', s)) + ' ' if re.search(r'[^\W_]', s) else ''


class Slides(HTMLParser):
    """Text runs per slide. A run ends at a block boundary."""

    def __init__(self, cls):
        super().__init__(convert_charrefs=True)
        self.cls, self.slides, self.depth, self.skip, self.cur = cls, [], 0, 0, []
        self.sections, self.sec_depth, self.use_sections = [], 0, False

    def _flush(self, bucket):
        if self.cur:
            t = ' '.join(''.join(self.cur).split())
            if t:
                bucket.append(t)
            self.cur = []

    def _bucket(self):
        if self.depth:
            return self.slides[-1]
        if self.sec_depth:
            return self.sections[-1]
        return None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        b = self._bucket()
        if b is not None and tag not in INLINE:
            self._flush(b)
        elif b is not None and tag in ('tspan', 'wbr'):
            self.cur.append(' ')              # a wrapped line of one label
        if tag in SKIP and tag not in VOID:
            self.skip += 1
        classes = (a.get('class') or '').split()
        if self.depth:
            if tag not in VOID:
                self.depth += 1
        elif self.cls in classes:
            self.slides.append([])
            self.depth = 1
        if self.sec_depth:
            if tag not in VOID:
                self.sec_depth += 1
        elif tag == 'section':
            self.sections.append([])
            self.sec_depth = 1
        if a.get('aria-hidden') == 'true' and tag not in VOID:
            pass

    def handle_endtag(self, tag):
        b = self._bucket()
        if b is not None and tag not in INLINE:
            self._flush(b)
        elif b is not None and tag == 'tspan':
            self.cur.append(' ')
        if tag in SKIP and self.skip:
            self.skip -= 1
        if tag in VOID:
            return
        if self.depth:
            self.depth -= 1
            if not self.depth:
                self._flush(self.slides[-1])
        if self.sec_depth:
            self.sec_depth -= 1
            if not self.sec_depth:
                self._flush(self.sections[-1])

    def handle_data(self, data):
        if self.skip or self._bucket() is None:
            return
        self.cur.append(data)


def slide_runs(path, n, cls):
    p = Slides(cls)
    with open(path, encoding='utf-8') as fh:
        p.feed(fh.read())
    p.close()
    pool = p.slides if p.slides else p.sections
    if not 1 <= n <= len(pool):
        sys.exit(f'check_labels: {path} has {len(pool)} slides, no slide {n}')
    return pool[n - 1]


def main():
    ap = argparse.ArgumentParser(description='Source labels kept on the animated slide.')
    ap.add_argument('before')
    ap.add_argument('after')
    ap.add_argument('--slide', type=int, required=True)
    ap.add_argument('--selector', default='slide', help='class that marks a slide (default: slide)')
    ap.add_argument('--allow')
    a = ap.parse_args()
    before = slide_runs(a.before, a.slide, a.selector)
    after = slide_runs(a.after, a.slide, a.selector)
    hay = squash(' '.join(after))
    allow = set()
    if a.allow:
        with open(a.allow, encoding='utf-8') as fh:
            allow = {squash(ln) for ln in fh if ln.strip() and not ln.lstrip().startswith('#')}
    missing, seen = [], set()
    for run in before:
        key = squash(run)
        if not key or key in seen:
            continue
        seen.add(key)
        if key in hay or key in allow:
            continue
        # a run may be split on the animated slide (a label and its value drawn apart): every
        # sentence-sized piece must still be there
        pieces = [x for x in re.split(r'\s*[·|•:]\s+', run) if squash(x)]
        if len(pieces) > 1 and all(squash(x) in hay for x in pieces):
            continue
        near = difflib.get_close_matches(run, after, n=1, cutoff=0.4)
        missing.append((run, near[0] if near else None))
    if not missing:
        print(f'OK   labels: all {len(seen)} text runs of slide {a.slide} are on the animated slide')
        return
    for run, near in missing:
        print(f'FAIL labels: "{run}" is not on the animated slide'
              + (f' (closest: "{near}")' if near else '') + '. Show it word for word, or keep the '
              'slide\'s own text beside the figure')
    print(f'FAILED: {len(missing)} of {len(seen)} source text runs missing')
    sys.exit(1)


if __name__ == '__main__':
    main()
