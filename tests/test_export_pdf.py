"""export_pdf.py through the real CLI: one page per slide on Letter and A4, labels kept.

python3 -m unittest discover -s tests -v   (from the repo root)
Skipped without Chrome or poppler.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'scripts', 'export_pdf.py')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import export_pdf  # noqa: E402

READY = bool(export_pdf.find_chrome()) and all(shutil.which(t) for t in ('pdftotext', 'pdftoppm', 'pdfinfo'))

FIXED = '''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;font:40px sans-serif}
.slide{width:1920px;height:1080px;padding:100px;box-sizing:border-box;position:relative}
@media print{.slide{width:1920px;height:1080px;break-after:page}}
.gone{opacity:0}
</style></head><body>
<section class="slide"><h1>Water cycle</h1><p>Evaporation lifts water into the air.</p></section>
<section class="slide"><h1>Three steps</h1>%s
<svg viewBox="0 0 800 200" width="800"><text x="20" y="60" font-size="30">Rain falls</text>
<text class="gone" x="20" y="120" font-size="30">Clouds form first</text></svg></section>
<section class="slide"><h1>Rivers return it</h1></section>
</body></html>'''

FLUID_TALL = '''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0}.slide{height:100vh}.tall{height:3000px}
</style></head><body>
<section class="slide"><h1>One</h1><div class="tall">far too tall</div></section>
<section class="slide"><h1>Two</h1></section></body></html>'''


@unittest.skipUnless(READY, 'needs Chrome and poppler')
class ExportPdfTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='export-pdf-test.')
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, text):
        p = os.path.join(self.tmp.name, name)
        with open(p, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return p

    def run_cli(self, deck, *extra):
        return subprocess.run([sys.executable, SCRIPT, deck, '--out', self.tmp.name] + list(extra),
                              capture_output=True, text=True)

    def info(self, pdf):
        out = subprocess.run(['pdfinfo', os.path.join(self.tmp.name, pdf)],
                             capture_output=True, text=True).stdout
        return {k.strip(): v.strip() for k, v in (ln.split(':', 1) for ln in out.splitlines() if ':' in ln)}

    def text(self, pdf, page):
        return subprocess.run(['pdftotext', '-f', str(page), '-l', str(page),
                               os.path.join(self.tmp.name, pdf), '-'],
                              capture_output=True, text=True).stdout

    def test_one_page_per_slide_on_both_papers(self):
        r = self.run_cli(self.write('deck.html', FIXED % ''))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        letter, a4 = self.info('deck-letter.pdf'), self.info('deck-a4.pdf')
        self.assertEqual(letter['Pages'], '3')
        self.assertEqual(a4['Pages'], '3')
        self.assertIn('792 x 612', letter['Page size'])
        self.assertIn('A4', a4['Page size'])

    def test_label_seen_only_during_the_pass_is_printed_under_its_slide(self):
        r = self.run_cli(self.write('deck.html', FIXED % ''), '--paper', 'letter')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('on screen only during the animation', r.stdout)
        page2 = self.text('deck-letter.pdf', 2)
        self.assertIn('Clouds form first', page2)
        self.assertIn('Shown during the animation', page2)
        self.assertNotIn('Shown during the animation', self.text('deck-letter.pdf', 1))

    def test_source_words_the_figure_reworded_are_kept(self):
        static = self.write('static.html', FIXED % '<ol><li>Rain falls on the hills.</li></ol>')
        r = self.run_cli(self.write('deck.html', FIXED % ''), '--paper', 'a4', '--source', static)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        page2 = self.text('deck-a4.pdf', 2)
        self.assertIn('Source text', page2)
        self.assertIn('Rain falls on the hills.', page2)
        self.assertEqual(self.info('deck-a4.pdf')['Pages'], '3')

    def test_slide_that_spills_over_its_page_fails(self):
        r = self.run_cli(self.write('tall.html', FLUID_TALL), '--paper', 'letter')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('pages:', r.stdout)


class LabelTest(unittest.TestCase):
    def test_labels_per_slide_skip_what_is_not_drawn(self):
        labels, ends = export_pdf.slide_labels(
            '<section class="slide"><h1>A <b>b</b></h1><svg><title>no</title><desc>no</desc>'
            '<text>Yes</text></svg><span class="sr-only">no</span></section>'
            '<section class="slide"><p>Two</p></section>', '.slide')
        self.assertEqual(labels, [['A', 'b', 'Yes'], ['Two']])
        self.assertEqual(len(ends), 2)

    def test_stage_is_read_from_the_print_rules(self):
        self.assertEqual(export_pdf.detect_stage('<style>@media print{@page{size:1280px 720px}}</style>'),
                         (1280, 720))
        self.assertEqual(export_pdf.detect_stage(FIXED), (1920, 1080))
        self.assertIsNone(export_pdf.detect_stage(FLUID_TALL))


if __name__ == '__main__':
    unittest.main()
