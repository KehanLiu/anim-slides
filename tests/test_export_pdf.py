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


class Base(unittest.TestCase):
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


@unittest.skipUnless(READY, 'needs Chrome and poppler')
class ExportPdfTest(Base):
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


TABLE = '''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;font:40px sans-serif}
.slide{width:1920px;height:1080px;padding:100px;box-sizing:border-box}
td,th{padding:10px 60px;text-align:left}
</style></head><body>
<section class="slide"><h1>Blood counts</h1><table>
<tr><th>Group</th><th>Week 1</th><th>Week 2</th></tr>
<tr><td>Control</td><td>12</td><td>12</td></tr>
<tr><td>Treated</td><td>12</td><td%s>9</td></tr>
<tr><td>Placebo</td><td%s>12</td><td>12</td></tr>
</table></section></body></html>'''

NOTES = '''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;font:40px sans-serif}
.slide{width:1920px;height:1080px;padding:100px;box-sizing:border-box}
.notes{display:none}
</style></head><body>
<section class="slide"><h1>Quarter results</h1><p>Revenue grew in the north.</p>
<aside class="notes">Do not mention the pending merger.</aside>
<div data-presenter-only>Skip this slide if short on time.</div></section>
<section class="slide"><h1>Next steps</h1>
<p class="speaker-notes" style="display:block">Pause here for questions.</p></section>
</body></html>'''

NOTE_ECHO = '''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;font:40px sans-serif}
.slide{width:1920px;height:1080px;padding:100px;box-sizing:border-box}
</style></head><body>
<section class="slide"><h1>Delivery times</h1><p>Old check 15 minutes. New check 3 minutes.</p>
<aside class="notes"%s>Delivery times</aside></section>
</body></html>'''

TABLE_PAIR = '''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;font:40px sans-serif}
.slide{width:1920px;height:1080px;padding:100px;box-sizing:border-box}
table{display:inline-table;margin-right:120px}td,th{padding:10px 30px;text-align:left}
</style></head><body>
<section class="slide"><h1>Two batches</h1><p>Morning and afternoon</p>
<table><tr><th>Group</th><th>Minutes</th></tr><tr><td>Standard</td><td>12</td></tr></table>
<table><tr><th>Group</th><th>Minutes</th></tr><tr><td>Standard</td><td%s>12</td></tr></table>
</section></body></html>'''


@unittest.skipUnless(READY, 'needs Chrome and poppler')
class PrintFlowTest(Base):
    """The browser's own Print on a deck that carries the installed rule: no export script,
    no paper-specific scale. Chrome's command line prints on Letter; for A4 the test adds the
    paper size alone, which is what choosing A4 in the print dialog does."""

    def browser_print(self, deck, paper):
        with open(deck, encoding='utf-8') as fh:
            page = fh.read()
        if paper == 'a4':
            # after the deck's rule, as the dialog's paper choice also overrides it
            page = page.replace('</body>', '<style>@page{size:A4 landscape}</style></body>', 1)
        copy = self.write('printed-%s.html' % paper, page)
        pdf = 'printed-%s.pdf' % paper
        self.assertTrue(export_pdf.print_pdf(export_pdf.find_chrome(), copy,
                                             os.path.join(self.tmp.name, pdf)))
        return pdf

    def assert_fits(self, pdf, pages, size):
        info = self.info(pdf)
        self.assertEqual(info['Pages'], str(pages))
        self.assertIn(size, info['Page size'])
        for pw, ph, words in export_pdf.pdf_pages(os.path.join(self.tmp.name, pdf)):
            self.assertTrue(words)
            for word, x0, y0, x1, y1 in words:
                self.assertTrue(-0.5 <= x0 and x1 <= pw + 0.5 and -0.5 <= y0 and y1 <= ph + 0.5,
                                '"%s" is off the page' % word)
            # the slide fills the page width: its text reaches past the middle of the page
            self.assertGreater(max(w[3] for w in words), pw * 0.25)

    def check_deck(self, body, strip):
        deck = self.write('deck.html', body)
        r = self.run_cli(deck, '--install')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('installed the print rule', r.stdout)
        for paper, size in (('letter', '792 x 612'), ('a4', 'A4')):
            pdf = self.browser_print(deck, paper)
            self.assert_fits(pdf, 3, size)
            self.assertIn('Rain falls', self.text(pdf, 2))
            self.assertEqual('Clouds form first' in self.text(pdf, 2), strip)
        return deck

    def test_static_deck_fits_letter_and_a4_from_the_browser(self):
        self.check_deck(FIXED.replace('<text class="gone" x="20" y="120" font-size="30">Clouds form first</text>', '')
                        % '<ol><li>Rain falls on the hills.</li></ol>', strip=False)

    def test_animated_deck_fits_letter_and_a4_from_the_browser(self):
        self.check_deck(FIXED % '', strip=True)

    def test_deck_without_the_rule_does_not_fit(self):
        # the fault the rule fixes: a 1920 px slide on a Letter page loses its right side
        pdf = self.browser_print(self.write('deck.html', FIXED % ''), 'letter')
        self.assertNotIn('792 x 612', self.info(pdf)['Page size'])

    def test_install_twice_leaves_one_rule_and_one_strip(self):
        deck = self.check_deck(FIXED % '', strip=True)
        self.assertEqual(self.run_cli(deck, '--install').returncode, 0)
        with open(deck, encoding='utf-8') as fh:
            page = fh.read()
        self.assertEqual(page.count(export_pdf.START), 1)
        self.assertEqual(page.count('class="anim-print-band"'), 1)

    def test_install_is_refused_when_the_export_fails(self):
        deck = self.write('tall.html', FLUID_TALL)
        r = self.run_cli(deck, '--install', '--paper', 'letter')
        self.assertEqual(r.returncode, 1)
        with open(deck, encoding='utf-8') as fh:
            self.assertEqual(fh.read(), FLUID_TALL)


@unittest.skipUnless(READY, 'needs Chrome and poppler')
class NotesTest(Base):
    def test_presenter_notes_stay_out_of_the_handout(self):
        r = self.run_cli(self.write('deck.html', NOTES), '--paper', 'letter')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('3 presenter notes left out', r.stdout)
        self.assertNotIn('strip:', r.stdout)
        everything = self.text('deck-letter.pdf', 1) + self.text('deck-letter.pdf', 2)
        self.assertIn('Revenue grew in the north.', everything)
        for secret in ('merger', 'short on time', 'Pause here'):
            self.assertNotIn(secret, everything)

    def test_note_that_repeats_the_title_passes(self):
        # the note is hidden in print; "Delivery times" is on the page once, as the title
        r = self.run_cli(self.write('deck.html', NOTE_ECHO % ''), '--paper', 'letter')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('1 presenter notes left out', r.stdout)
        self.assertEqual(self.text('deck-letter.pdf', 1).count('Delivery times'), 1)

    def test_note_that_repeats_the_title_fails_when_printed(self):
        r = self.run_cli(self.write('deck.html', NOTE_ECHO % ' style="display:block!important"'),
                         '--paper', 'letter')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('notes: slide 1, the presenter note "Delivery times" is on page 1', r.stdout)

    def test_notes_are_not_source_labels_either(self):
        static = self.write('static.html', NOTES)
        r = self.run_cli(self.write('deck.html', NOTES), '--paper', 'a4', '--source', static)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn('merger', self.text('deck-a4.pdf', 1))


@unittest.skipUnless(READY, 'needs Chrome and poppler')
class TableTest(Base):
    HIDE = ' style="visibility:hidden"'

    def test_repeated_values_pass_when_every_cell_is_drawn(self):
        r = self.run_cli(self.write('deck.html', TABLE % ('', '')), '--paper', 'letter')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_missing_repeat_is_named_by_its_cell(self):
        # five cells say 12; with one hidden, "12" is still on the page four times
        r = self.run_cli(self.write('deck.html', TABLE % ('', self.HIDE)), '--paper', 'letter')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('table: slide 1, table 1, row 4 column 2: "12" is not drawn in its cell', r.stdout)

    def test_a_missing_single_value_is_named_by_its_cell(self):
        r = self.run_cli(self.write('deck.html', TABLE % (self.HIDE, '')), '--paper', 'a4')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('row 3 column 3: "9"', r.stdout)

    def test_two_tables_with_the_same_values_pass_when_both_are_drawn(self):
        r = self.run_cli(self.write('deck.html', TABLE_PAIR % ''), '--paper', 'letter')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_one_table_cannot_stand_in_for_another(self):
        # both tables say "Standard 12"; the second 12 is hidden, so the page has one 12
        r = self.run_cli(self.write('deck.html', TABLE_PAIR % self.HIDE), '--paper', 'letter')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('table: slide 1, table 2, row 2 column 2: "12" is not drawn in its cell', r.stdout)
        self.assertIn('9 of 10 labels on their page', r.stdout)

    def test_tables_share_no_drawn_words(self):
        words = [('group', 10, 10, 60, 20), ('n', 100, 10, 110, 20),
                 ('a', 10, 40, 20, 50), ('12', 100, 40, 115, 50)]
        table = {'rows': [['Group', 'N'], ['A', '12']], 'spans': False}
        self.assertEqual(export_pdf.place_tables([table], words)[0], None)
        self.assertEqual(export_pdf.place_tables([table, table], words)[0], (1, 0, 0, 'Group'))
        twice = words + [(w, x0 + 300, y0, x1 + 300, y1) for w, x0, y0, x1, y1 in words]
        bad, used = export_pdf.place_tables([table, table], twice)
        self.assertIsNone(bad)
        self.assertEqual(used, set(range(8)))

    def test_value_in_the_wrong_column_is_not_accepted(self):
        words = [('group', 10, 10, 60, 20), ('a', 100, 10, 110, 20), ('b', 200, 10, 210, 20),
                 ('x', 10, 40, 20, 50), ('12', 200, 40, 215, 50), ('7', 100, 40, 108, 50)]
        table = {'rows': [['Group', 'A', 'B'], ['x', '12', '7']], 'spans': False}
        self.assertEqual(export_pdf.place_table(table, words), (1, 1, '12'))
        table['rows'][1] = ['x', '7', '12']
        self.assertIsNone(export_pdf.place_table(table, words))


@unittest.skipUnless(READY, 'needs Chrome and poppler')
class ReplaceTest(Base):
    def test_existing_pdf_survives_a_failing_export(self):
        old = self.write('tall-letter.pdf', 'the last good export')
        r = self.run_cli(self.write('tall.html', FLUID_TALL), '--paper', 'letter')
        self.assertEqual(r.returncode, 1)
        with open(old, encoding='utf-8') as fh:
            self.assertEqual(fh.read(), 'the last good export')
        self.assertIn('is unchanged', r.stdout)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp.name, 'tall-letter.rejected.pdf')))
        self.assertEqual([f for f in os.listdir(self.tmp.name) if f.startswith('.')], [])

    def test_existing_pdf_is_replaced_by_a_passing_export(self):
        old = self.write('deck-letter.pdf', 'the last good export')
        self.write('deck-letter.rejected.pdf', 'an earlier failure')
        r = self.run_cli(self.write('deck.html', FIXED % ''), '--paper', 'letter')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(old, 'rb') as fh:
            self.assertTrue(fh.read().startswith(b'%PDF'))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, 'deck-letter.rejected.pdf')))


class LabelTest(unittest.TestCase):
    def test_labels_per_slide_skip_what_is_not_drawn(self):
        labels, ends = export_pdf.slide_labels(
            '<section class="slide"><h1>A <b>b</b></h1><svg><title>no</title><desc>no</desc>'
            '<text>Yes</text></svg><span class="sr-only">no</span>'
            '<aside class="notes">no</aside></section>'
            '<section class="slide"><p>Two</p></section>', '.slide')
        self.assertEqual(labels, [['A', 'b', 'Yes'], ['Two']])
        self.assertEqual(len(ends), 2)

    def test_note_counts_only_beyond_the_labels(self):
        page = [export_pdf.squash('Delivery times Old check 15 minutes.')]
        labels = ['Delivery times', 'Old check 15 minutes.']
        self.assertFalse(export_pdf.printed_more_often('Delivery times', labels, page))
        page = [export_pdf.squash('Delivery times Old check 15 minutes. Delivery times')]
        self.assertTrue(export_pdf.printed_more_often('Delivery times', labels, page))

    def test_stage_is_read_from_the_print_rules(self):
        self.assertEqual(export_pdf.detect_stage('<style>@media print{@page{size:1280px 720px}}</style>'),
                         (1280, 720))
        self.assertEqual(export_pdf.detect_stage(FIXED), (1920, 1080))
        self.assertIsNone(export_pdf.detect_stage(FLUID_TALL))


if __name__ == '__main__':
    unittest.main()
