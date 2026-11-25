"""check_labels.py: every text run of the source slide is still on the animated slide."""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'scripts', 'check_labels.py')

BEFORE = '''<!doctype html><html><body>
<div class="slide"><h1>Title slide</h1></div>
<div class="slide"><h2>Waiting time by clinic</h2>
<table><tr><th>Clinic</th><th>Median wait</th></tr>
<tr><td>Harbour Street walk-in centre</td><td>45 minutes</td></tr>
<tr><td>Northside</td><td>2 hours</td></tr></table></div>
</body></html>'''


def after(body):
    return ('<!doctype html><html><body><div class="slide"><h1>Title slide</h1></div>'
            '<div class="slide"><h2>Waiting time by clinic</h2>' + body + '</div></body></html>')


FULL = ('<svg viewBox="0 0 800 400"><text>Clinic</text><text>Median wait</text>'
        '<text><tspan x="0">Harbour Street</tspan><tspan x="0" dy="30">walk-in centre</tspan></text>'
        '<text>45 minutes</text><text>Northside</text><text>2 hours</text></svg>')


class CheckLabels(unittest.TestCase):
    def run_check(self, after_html, *extra):
        with tempfile.TemporaryDirectory() as d:
            b, a = os.path.join(d, 'before.html'), os.path.join(d, 'after.html')
            with open(b, 'w', encoding='utf-8') as f:
                f.write(BEFORE)
            with open(a, 'w', encoding='utf-8') as f:
                f.write(after_html)
            args = [x.replace('{dir}', d) for x in extra]
            for x in args:
                if x.endswith('allow.txt'):
                    with open(x, 'w', encoding='utf-8') as f:
                        f.write('Median wait\n')
            return subprocess.run([sys.executable, SCRIPT, b, a, '--slide', '2', *args],
                                  capture_output=True, text=True)

    def test_unchanged_slide_passes(self):
        self.assertEqual(self.run_check(BEFORE).returncode, 0)

    def test_label_wrapped_over_tspans_passes(self):
        r = self.run_check(after(FULL))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_shortened_label_fails(self):
        r = self.run_check(after(FULL.replace('<tspan x="0" dy="30">walk-in centre</tspan>', '')))
        self.assertEqual(r.returncode, 1)
        self.assertIn('Harbour Street walk-in centre', r.stdout)

    def test_changed_unit_fails(self):
        r = self.run_check(after(FULL.replace('2 hours', '2 h')))
        self.assertEqual(r.returncode, 1)
        self.assertIn('2 hours', r.stdout)

    def test_dropped_table_heading_fails_and_allow_lets_it_go(self):
        dropped = after(FULL.replace('<text>Median wait</text>', ''))
        r = self.run_check(dropped)
        self.assertEqual(r.returncode, 1)
        self.assertIn('Median wait', r.stdout)
        r = self.run_check(dropped, '--allow', '{dir}/allow.txt')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()
