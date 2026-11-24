"""verify_facts.py label-value pairing, run through the real CLI as a user runs it.

python3 -m unittest discover -s tests -v   (from the repo root)
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'scripts', 'verify_facts.py')
SOURCE = 'Checkout latency: 200 ms\nSearch latency: 80 ms'


class PairingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='verify-facts-test.')
        self.addCleanup(self.tmp.cleanup)

    def run_cli(self, body, *extra, source=SOURCE, strict=True):
        frag = os.path.join(self.tmp.name, 'fragment.html')
        with open(frag, 'w', encoding='utf-8') as fh:
            fh.write('<svg viewBox="0 0 400 200">' + body + '</svg>')
        args = [sys.executable, SCRIPT, frag]
        if source is not None:
            args += ['--source-text', source]
        args += list(extra) + (['--strict'] if strict else [])
        r = subprocess.run(args, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def lines(self, out, level, check):
        return [ln for ln in out.splitlines() if ln.startswith(f'{level:<4} {check}:')]

    # (a) swapped values
    def test_swapped_values_fail_under_strict(self):
        code, out = self.run_cli('<text x="10" y="20">Checkout latency: 80 ms</text>'
                                 '<text x="10" y="50">Search latency: 200 ms</text>')
        self.assertEqual(code, 1, out)
        fails = self.lines(out, 'FAIL', 'pairing')
        self.assertEqual(len(fails), 2, out)
        checkout = next(ln for ln in fails if "'Checkout" in ln)
        self.assertIn('shows 80 ms', checkout)
        self.assertIn('the source gives 200 ms', checkout)
        self.assertIn('Search latency: 80 ms', checkout)

    def test_swapped_values_warn_without_strict(self):
        code, out = self.run_cli('<text x="10" y="20">Checkout latency: 80 ms</text>'
                                 '<text x="10" y="50">Search latency: 200 ms</text>', strict=False)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.lines(out, 'WARN', 'pairing')), 2, out)

    def test_swap_in_separate_texts_fails(self):
        code, out = self.run_cli('<text x="10" y="20">Checkout</text><text x="200" y="20">80 ms</text>'
                                 '<text x="10" y="50">Search</text><text x="200" y="50">200 ms</text>')
        self.assertEqual(code, 1, out)
        self.assertEqual(len(self.lines(out, 'FAIL', 'pairing')), 2, out)

    def test_swap_against_outline_table_fails(self):
        outline = os.path.join(self.tmp.name, 'outline.json')
        with open(outline, 'w', encoding='utf-8') as fh:
            json.dump({'slides': [{'index': 1, 'title': 'Latency by service', 'tables': [[
                ['Service', 'p95 latency', 'Error rate'],
                ['Checkout', '200 ms', '2 %'],
                ['Search', '80 ms', '1 %']]]}]}, fh)
        swapped = ('<text x="10" y="20">Checkout</text><text x="200" y="20">80 ms</text>'
                   '<text x="10" y="50">Search</text><text x="200" y="50">200 ms</text>')
        code, out = self.run_cli(swapped, '--source', outline, '--slide', '1', source=None)
        self.assertEqual(code, 1, out)
        self.assertTrue(self.lines(out, 'FAIL', 'pairing'), out)
        right = ('<text x="10" y="20">Checkout</text><text x="200" y="20">200 ms</text>'
                 '<text x="300" y="20">2 %</text>'
                 '<text x="10" y="50">Search</text><text x="200" y="50">80 ms</text>'
                 '<text x="300" y="50">1 %</text>')
        code, out = self.run_cli(right, '--source', outline, '--slide', '1', source=None)
        self.assertEqual(code, 0, out)
        self.assertFalse([ln for ln in out.splitlines() if 'pairing' in ln and not ln.startswith('OK')], out)

    # (b) (c) (d) correct pairs in the usual layouts
    def assert_clean_pairs(self, body, n=2):
        code, out = self.run_cli(body)
        self.assertEqual(code, 0, out)
        self.assertIn('PASS: 0 fail, 0 warn', out)
        self.assertIn(f'OK   pairing: {n} numbers beside the label', out)

    def test_correct_pairs_in_source_order(self):
        self.assert_clean_pairs('<text x="10" y="20">Checkout latency: 200 ms</text>'
                                '<text x="10" y="50">Search latency: 80 ms</text>')

    def test_correct_pairs_reordered(self):
        self.assert_clean_pairs('<text x="10" y="20">Search latency: 80 ms</text>'
                                '<text x="10" y="50">Checkout latency: 200 ms</text>')

    def test_correct_pairs_separate_texts_same_row(self):
        self.assert_clean_pairs('<text x="10" y="20">Search</text><text x="200" y="20">80 ms</text>'
                                '<text x="10" y="50">Checkout</text><text x="200" y="50">200 ms</text>')

    def test_correct_pairs_separate_texts_same_column(self):
        self.assert_clean_pairs('<text x="50" y="20">Checkout</text><text x="50" y="60">200 ms</text>'
                                '<text x="250" y="20">Search</text><text x="250" y="60">80 ms</text>')

    def test_correct_pairs_shared_group(self):
        self.assert_clean_pairs('<g transform="translate(0,20)"><text>Search</text><text>80 ms</text></g>'
                                '<g transform="translate(0,50)"><text>Checkout</text><text>200 ms</text></g>')

    def test_correct_pairs_value_in_tspan(self):
        self.assert_clean_pairs('<text x="10" y="20">Search <tspan class="v">80 ms</tspan></text>'
                                '<text x="10" y="50">Checkout <tspan class="v">200 ms</tspan></text>')

    # (e) ambiguity is flagged for review, never failed
    def test_value_equally_near_two_labels_is_review_warn(self):
        code, out = self.run_cli('<text x="10" y="20">Checkout</text><text x="10" y="60">Search</text>'
                                 '<text x="10" y="40">80 ms</text>')
        self.assertEqual(code, 0, out)
        warns = self.lines(out, 'WARN', 'pairing')
        self.assertEqual(len(warns), 1, out)
        self.assertIn('review', warns[0])
        self.assertIn('equally near', warns[0])

    def test_label_with_several_source_values_is_review_warn(self):
        src = 'Checkout latency: 200 ms\nCheckout latency target: 150 ms\nSearch latency: 80 ms'
        code, out = self.run_cli('<text x="10" y="20">Checkout latency: 80 ms</text>', source=src)
        self.assertEqual(code, 0, out)
        warns = self.lines(out, 'WARN', 'pairing')
        self.assertEqual(len(warns), 1, out)
        self.assertIn('review', warns[0])
        self.assertIn('several values', warns[0])
        # either of the label's values is a correct pairing
        code, out = self.run_cli('<text x="10" y="20">Checkout latency: 150 ms</text>', source=src)
        self.assertEqual(code, 0, out)
        self.assertIn('PASS: 0 fail, 0 warn', out)

    def test_prose_source_does_not_pair(self):
        code, out = self.run_cli('<text x="10" y="20">Latency: 200 ms</text>'
                                 '<text x="10" y="50">Latency: 80 ms</text>',
                                 source='Latency rose from 80 ms to 200 ms after the release')
        self.assertFalse([ln for ln in out.splitlines() if 'pairing' in ln], out)

    # (f) pre-existing behaviour
    def test_invented_number_still_fails(self):
        code, out = self.run_cli('<text x="10" y="20">Checkout latency: 95 ms</text>'
                                 '<text x="10" y="50">Search latency: 80 ms</text>')
        self.assertEqual(code, 1, out)
        self.assertTrue(any('95' in ln and 'not in the source' in ln
                            for ln in self.lines(out, 'FAIL', 'numbers')), out)

    def test_invented_number_fails_without_strict(self):
        code, out = self.run_cli('<text x="10" y="20">Checkout latency: 95 ms</text>', strict=False)
        self.assertEqual(code, 1, out)

    def test_builtin_self_test_passes(self):
        r = subprocess.run([sys.executable, SCRIPT, '--self-test'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('self-test: all passed', r.stdout)


if __name__ == '__main__':
    unittest.main()
