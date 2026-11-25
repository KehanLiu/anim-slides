"""Duration race (scripts/race_figure.py): one value changes, everything drawn follows."""
import copy
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import race_figure as rf  # noqa: E402

SPEC = {
    'name': 'ferry-or-bridge', 'archetype': 'durations', 'unit': 'min', 'status': 'illustrative',
    'claim': 'The ferry takes 30 minutes longer',
    'bars': [{'label': 'Bridge', 'value': 15}, {'label': 'Ferry', 'value': 45}],
}


def rf_write(path, spec):
    import json
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(spec, fh)


def rf_read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def with_value(spec, label, value, **more):
    s = copy.deepcopy(spec)
    for b in s['bars']:
        if b['label'] == label:
            b['value'] = value
    s.update(more)
    return s


class UpdateTogether(unittest.TestCase):
    def test_bars_share_one_scale_and_one_speed(self):
        F = rf.plan(SPEC)
        a, b = F.bars
        self.assertAlmostEqual((F.X(b.v) - F.x0) / (F.X(a.v) - F.x0), 3.0)
        self.assertAlmostEqual((b.t1 - F.T0) / (a.t1 - F.T0), 3.0)
        self.assertEqual((F.hero, F.hero_words), ('30', 'minutes longer'))

    def test_one_changed_value_moves_geometry_timing_and_takeaway(self):
        before = rf.plan(SPEC)
        after = rf.plan(with_value(SPEC, 'Ferry', 60, claim='The ferry takes 45 minutes longer'))
        self.assertEqual(after.hero, '45')
        self.assertAlmostEqual(after.X(60), after.x0 + after.scale * 60)
        # the bridge did not change, yet its bar and its stop time do: one scale, one speed
        self.assertLess(after.X(15), before.X(15))
        self.assertLess(after.bars[0].t1, before.bars[0].t1)
        self.assertAlmostEqual((after.bars[1].t1 - after.T0) / (after.bars[0].t1 - after.T0), 4.0)
        html = rf.render(after)
        self.assertIn('>45</text>', html)
        self.assertIn('60 min', html)
        self.assertEqual(html.count('>45</text>'), 2)
        self.assertNotIn('30 min', re.sub(r'<style>.*?</style>|<!--.*?-->', '', html, flags=re.S))

    def test_stale_claim_stops_the_build(self):
        with self.assertRaises(rf.SpecError) as cm:
            rf.plan(with_value(SPEC, 'Ferry', 60))
        self.assertIn('30', str(cm.exception))
        self.assertIn('difference 45', str(cm.exception))

    def test_order_can_flip(self):
        F = rf.plan(with_value(SPEC, 'Ferry', 5, claim=None))
        self.assertEqual((F.long.label, F.short.label), ('Bridge', 'Ferry'))
        self.assertEqual((F.kind, F.hero), ('ratio', '3×'))


class Units(unittest.TestCase):
    def test_mixed_units_convert_and_keep_the_label_as_written(self):
        F = rf.plan({'name': 'rise', 'archetype': 'durations', 'status': 'illustrative', 'bars': [
            {'label': 'Warm', 'value': '90 min'}, {'label': 'Cold', 'value': '18 h'},
            {'label': 'Long', 'value': '1 h 30 min'}]})
        self.assertEqual(F.unit, 'h')
        self.assertEqual([round(b.v, 6) for b in F.bars], [1.5, 18, 1.5])
        self.assertEqual(F.bars[0].shown, '90 min')
        self.assertEqual(F.hero, '12×')

    def test_months_against_days_need_a_stated_length(self):
        spec = {'name': 'cal', 'archetype': 'durations', 'status': 'real', 'unit': 'days', 'bars': [
            {'label': 'A', 'value': 10}, {'label': 'B', 'value': 2, 'unit': 'months'}]}
        with self.assertRaises(rf.SpecError):
            rf.plan(spec)
        F = rf.plan(dict(spec, calendar={'month': 30}))
        self.assertEqual(F.bars[1].v, 60)
        self.assertIn('1 month = 30 days', rf.render(F))

    def test_extreme_ratio_stays_to_scale(self):
        F = rf.plan({'name': 'far', 'archetype': 'durations', 'status': 'real', 'unit': 's', 'bars': [
            {'label': 'A', 'value': 4}, {'label': 'B', 'value': 360}]})
        self.assertAlmostEqual((F.X(360) - F.x0) / (F.X(4) - F.x0), 90)
        self.assertEqual(F.hero, '90×')

    def test_stages_must_add_up(self):
        spec = {'name': 'st', 'archetype': 'durations', 'status': 'real', 'unit': 'months', 'bars': [
            {'label': 'A', 'value': 3}, {'label': 'B', 'value': 18, 'stages': [
                {'label': 'x', 'value': 4}, {'label': 'y', 'value': 13}]}]}
        with self.assertRaises(rf.SpecError):
            rf.plan(spec)

    def test_claim_numbers(self):
        ok = dict(SPEC, claim='The ferry takes three times as long, about 67 % more of your morning')
        with self.assertRaises(rf.SpecError):
            rf.plan(dict(SPEC, claim='The ferry takes twice as long'))
        self.assertEqual(rf.plan(ok).kind, 'ratio')


CHECK = {
    'name': 'check-race', 'archetype': 'durations', 'unit': 'min', 'status': 'real', 'takeaway': 'difference',
    'bars': [{'label': 'Old check', 'value': 15}, {'label': 'New check', 'value': 1}],
}


class ClaimIsBound(unittest.TestCase):
    """A number in the claim is tied to what the sentence says about it, not to any value it equals."""

    def test_saving_must_be_the_difference_not_a_bar_that_happens_to_match(self):
        claim = 'The new check saves 14 minutes.'
        self.assertEqual(rf.plan(dict(CHECK, claim=claim)).claim_review, [])
        with self.assertRaises(rf.SpecError) as cm:          # 15 against 14: the saving is 1, yet a bar is 14
            rf.plan(with_value(CHECK, 'New check', 14, claim=claim))
        self.assertIn('14 minutes', str(cm.exception))
        self.assertIn('difference 1 min', str(cm.exception))
        self.assertEqual(rf.plan(with_value(CHECK, 'New check', 14, claim='The new check takes 14 minutes.')).claim_review, [])

    def test_unit_of_the_claim_is_converted(self):
        self.assertEqual(rf.plan(dict(CHECK, claim='The new check saves 840 seconds')).claim_review, [])
        with self.assertRaises(rf.SpecError):
            rf.plan(dict(CHECK, claim='The new check saves 14 seconds'))

    def test_percent_and_multiple_do_not_match_a_bar(self):
        with self.assertRaises(rf.SpecError):
            rf.plan(dict(CHECK, claim='The new check is 15 % shorter'))
        self.assertEqual(rf.plan(dict(CHECK, claim='The new check is 15 times faster', takeaway='auto')).kind, 'ratio')

    def test_what_cannot_be_tied_down_is_flagged_for_review(self):
        wrong_way = rf.plan(dict(CHECK, claim='The new check takes 14 minutes longer'))
        self.assertIn('direction', wrong_way.claim_review[0])
        wrong_bar = rf.plan(dict(CHECK, claim='The new check takes 15 minutes'))
        self.assertIn('Old check', wrong_bar.claim_review[0])
        bare = rf.plan(dict(CHECK, claim='From 15 down to 1'))
        self.assertEqual(len(bare.claim_review), 2)
        self.assertIn('REVIEW claim', '\n'.join(rf.summary(wrong_way)))
        self.assertNotIn('every number in the sentence follows', '\n'.join(rf.summary(wrong_way)))


class InputIsReadWhole(unittest.TestCase):
    def read(self, value, unit=None):
        return rf.parse_duration(value, unit, 'bar')

    def test_leading_decimal_keeps_its_value_and_the_winner(self):
        self.assertEqual(self.read('.5 s'), [(0.5, 's')])
        F = rf.plan(dict(CHECK, unit='s', bars=[{'label': 'Old check', 'value': '2 s'}, {'label': 'New check', 'value': '.5 s'}]))
        self.assertEqual((F.long.label, F.hero), ('Old check', '1.5'))

    def test_negative_range_and_leftovers_are_refused(self):
        for bad in ('-3 min', '\u22123 min', '1 min to 3 min', '2-3 h', '5 \u2013 7 min', '1 min 3 min',
                    '3 min 1 h', '1,5 s', 'about 5 min', '5 min!', '+5 min', '1.5.2 s', ''):
            with self.assertRaises(rf.SpecError, msg=bad):
                self.read(bad)
        with self.assertRaises(rf.SpecError):
            rf.plan(with_value(CHECK, 'Old check', -3))
        with self.assertRaises(rf.SpecError):
            rf.plan(with_value(CHECK, 'Old check', float('nan')))

    def test_supported_compounds(self):
        self.assertEqual(self.read('1 h 30 min'), [(1, 'h'), (30, 'min')])
        self.assertEqual(self.read('1h30min'), [(1, 'h'), (30, 'min')])
        self.assertEqual(self.read('2 years and 3 months'), [(2, 'years'), (3, 'months')])
        self.assertEqual(self.read('1,200 ms'), [(1200, 'ms')])
        self.assertEqual(self.read('5', 'min'), [(5, 'min')])

    def test_endpoint_labels_keep_source_precision(self):
        F = rf.plan(dict(CHECK, unit='s', bars=[{'label': 'Old check', 'value': '1.04 s'}, {'label': 'New check', 'value': 1.01}]))
        self.assertEqual([b.shown for b in F.bars], ['1.04 s', '1.01 s'])
        self.assertEqual(F.hero, '0.03')
        self.assertEqual(rf.num(2.55 - 1.2), '1.35')
        self.assertEqual(rf.num(1 / 3), '0.33')
        self.assertEqual(rf.num(12000.5), '12,000.5')


class Cli(unittest.TestCase):
    def test_pool_fragment_is_what_its_spec_builds(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'mediation-vs-trial.html')
            r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'scaffold_from_spec.py'),
                                os.path.join(ROOT, 'pool', 'mediation-vs-trial', 'spec.yaml'), '-o', out],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('PASS: 0 fail, 0 warn', r.stdout)
            with open(out, encoding='utf-8') as a, open(os.path.join(
                    ROOT, 'pool', 'mediation-vs-trial', 'mediation-vs-trial.html'), encoding='utf-8') as b:
                self.assertEqual(a.read(), b.read())

    def test_failed_build_leaves_the_old_fragment(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, out = os.path.join(tmp, 'spec.json'), os.path.join(tmp, 'f.html')
            rf_write(spec, SPEC)
            cmd = [sys.executable, os.path.join(ROOT, 'scripts', 'race_figure.py'), spec, '-o', out]
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            first = rf_read(out)
            rf_write(spec, with_value(SPEC, 'Ferry', 60))
            r = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn('no longer follows', r.stderr)
            self.assertEqual(rf_read(out), first)

    def test_failing_check_leaves_the_last_good_fragment(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, out = os.path.join(tmp, 'spec.json'), os.path.join(tmp, 'f.html')
            rf_write(spec, dict(CHECK, size=[1680, 600]))
            cmd = [sys.executable, os.path.join(ROOT, 'scripts', 'scaffold_from_spec.py'), spec, '-o', out]
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            first = rf_read(out)
            rf_write(spec, with_value(CHECK, 'New check', 3, size=[1680, 600]))
            r = subprocess.run(cmd + ['--rendered-width', '900'], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)                 # text under the floor at this width
            self.assertIn('text-size', r.stdout)
            self.assertIn('is unchanged', r.stdout)
            self.assertEqual(rf_read(out), first)
            self.assertEqual(sorted(os.listdir(tmp)), ['f.html', 'spec.json'])     # no temporary file left
            fresh = os.path.join(tmp, 'new.html')                # a first build that fails creates nothing
            r = subprocess.run(cmd[:-1] + [fresh, '--rendered-width', '900'], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse(os.path.exists(fresh))


if __name__ == '__main__':
    unittest.main()
