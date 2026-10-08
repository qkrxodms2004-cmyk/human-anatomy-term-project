import csv
from dataclasses import replace
import random
import tempfile
import unittest
from pathlib import Path

import numpy as np
from sternberg import Settings, filtered_noise, load_settings, make_stimuli, noise_conditions, read_stimuli, validate_settings


class TaskTests(unittest.TestCase):
    def test_generated_sets_and_balanced_answers(self):
        rows = make_stimuli(24, 5, random.Random(42))
        self.assertEqual(sum(r['probe'] in r['set'] for r in rows), 12)
        for row in rows:
            self.assertEqual(len(set(row['set'])), 5)
            self.assertTrue(row['set'].isupper())
        self.assertEqual(rows, make_stimuli(24, 5, random.Random(42)))

    def test_noise_assignment_covers_twelve_conditions(self):
        rows = noise_conditions(24, random.Random(10))
        from collections import Counter
        counts = Counter(tuple(r.values()) for r in rows)
        self.assertEqual(len(counts), 12)
        self.assertEqual(set(counts.values()), {2})

    def test_audio_filters_rms_and_no_clipping(self):
        cfg = replace(Settings(), memorize_seconds=.2, delay_seconds=.2, response_timeout_seconds=.2)
        for band in ('low', 'high'):
            for level in ('quiet', 'loud'):
                audio = filtered_noise(cfg, band, level, 42)
                self.assertEqual(audio.dtype, np.int16)
                np.testing.assert_array_equal(audio[:, 0], audio[:, 1])
                wave = audio[:, 0].astype(float) / 32767
                self.assertAlmostEqual(np.sqrt(np.mean(wave ** 2)), getattr(cfg, level + '_rms'), places=5)
                self.assertLess(np.max(np.abs(wave)), 1)
                energy = abs(np.fft.rfft(wave)) ** 2
                f = np.fft.rfftfreq(len(wave), 1 / cfg.sample_rate)
                rejected = f > cfg.low_cutoff_hz if band == 'low' else f < cfg.high_cutoff_hz
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
        for overrides in ({'set_size': 26}, {'trials': 0}, {'delay_seconds': -1},
                          {'quiet_rms': .06}, {'high_cutoff_hz': 30000}, {'break_seconds': float('nan')}):
            with self.assertRaises(ValueError):
                validate_settings(replace(cfg, **overrides))


if __name__ == '__main__':
    unittest.main()
