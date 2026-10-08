import csv
from dataclasses import replace
import random
import tempfile
import unittest
from pathlib import Path

from vendor_loader import configure_vendor

configure_vendor()
import numpy as np
from sternberg import Settings, filtered_noise, load_settings, make_stimuli, noise_conditions, read_stimuli, validate_settings, validate_participant


class TaskTests(unittest.TestCase):
    def test_participant_id_validation(self):
        self.assertEqual(validate_participant(' P001-2_A '), 'P001-2_A')
        self.assertEqual(validate_participant('피험자01'), '피험자01')
        for value in ('', ' ', '../P001', 'P/001', 'P 001', 'P:001', '---', 'P' * 61):
            with self.assertRaises(ValueError):
                validate_participant(value)

    def test_generated_sets_and_balanced_answers(self):
        rows = make_stimuli(24, 5, random.Random(42))
        self.assertEqual(sum(r['probe'] in r['set'] for r in rows), 12)
        for row in rows:
            self.assertEqual(len(set(row['set'])), 5)
            self.assertTrue(row['set'].isupper())
        self.assertEqual(rows, make_stimuli(24, 5, random.Random(42)))

    def test_noise_assignment_covers_seven_conditions_equally(self):
        from collections import Counter
        expected = {'quiet', 'low_set', 'high_set', 'low_delay', 'high_delay', 'low_probe', 'high_probe'}
        for n in (1, 2, 5, 10):
            rows = noise_conditions(n, random.Random(10))
            self.assertEqual(len(rows), 7 * n)
            counts = Counter(r['noise_condition'] for r in rows)
            self.assertEqual(set(counts), expected)
            self.assertEqual(set(counts.values()), {n})
            self.assertEqual(rows, noise_conditions(n, random.Random(10)))
            self.assertEqual(replace(Settings(), trials_per_condition=n).trials, 7 * n)
        with self.assertRaises(ValueError):
            noise_conditions(0, random.Random(10))

    def test_audio_filters_rms_and_no_clipping(self):
        for limits in ((20, 1000, 4000, 12000), (200, 700, 2500, 5000)):
            cfg = replace(Settings(), memorize_seconds=.2, delay_seconds=.2, response_timeout_seconds=.2,
                          low_min_hz=limits[0], low_max_hz=limits[1], high_min_hz=limits[2], high_max_hz=limits[3])
            for band in ('low', 'high'):
                audio = filtered_noise(cfg, band, 42)
                self.assertEqual(audio.dtype, np.int16)
                np.testing.assert_array_equal(audio[:, 0], audio[:, 1])
                wave = audio[:, 0].astype(float) / 32767
                self.assertAlmostEqual(np.sqrt(np.mean(wave ** 2)), cfg.noise_rms, places=5)
                self.assertLess(np.max(np.abs(wave)), 1)
                energy = abs(np.fft.rfft(wave)) ** 2
                f = np.fft.rfftfreq(len(wave), 1 / cfg.sample_rate)
                rejected = (f < getattr(cfg, band + '_min_hz')) | (f > getattr(cfg, band + '_max_hz'))
                self.assertLess(energy[rejected].sum() / energy.sum(), 1e-5)

    def test_external_csv_and_reject_invalid_sets(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'stimuli.csv'
            path.write_text('set,probe\nABCDE,A\nFGHIJ,Z\n', encoding='utf-8-sig')
            self.assertEqual(read_stimuli(str(path), 2, 5)[1]['probe'], 'Z')
            with self.assertRaises(ValueError):
                read_stimuli(str(path), 3, 5)
            path.write_text('set,probe\nAABCD,A\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                read_stimuli(str(path), 1, 5)

    def test_settings_paths_and_invalid_values(self):
        cfg = load_settings(Path(__file__).with_name('config.ini'))
        self.assertTrue(Path(cfg.output_dir).is_absolute())
        for overrides in ({'set_size': 26}, {'trials_per_condition': 0}, {'delay_seconds': -1},
                          {'noise_rms': .2}, {'high_max_hz': 30000}, {'break_seconds': float('nan')},
                          {'low_min_hz': -1}, {'low_max_hz': 20}, {'high_min_hz': 500},
                          {'high_max_hz': float('nan')}):
            with self.assertRaises(ValueError):
                validate_settings(replace(cfg, **overrides))


if __name__ == '__main__':
    unittest.main()
