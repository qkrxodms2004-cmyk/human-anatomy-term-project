"""Headless integration checks of real Pygame event handling and CSV persistence."""
import csv
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

from sternberg import Experiment, QuitExperiment, Settings


class InterfaceTests(unittest.TestCase):
    def test_keys_timeout_and_noise_stage_recording(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg = replace(Settings(), output_dir=folder, seed=42, memorize_seconds=.02,
                          delay_seconds=.02, response_timeout_seconds=.07, intertrial_seconds=.01)
            task = Experiment(cfg, 'CHECK')
            try:
                task.setup()
                original_events = task.events
                for number, (answer, stage) in enumerate(((task.pg.K_LEFT, 'set'), (task.pg.K_RIGHT, 'delay'), (None, 'probe')), 1):
                    sent = [False]
                    def events():
                        row = task.active_row
                        if row and row['probe_onset_s'] != '' and not sent[0] and answer is not None:
                            task.pg.event.post(task.pg.event.Event(task.pg.KEYDOWN, key=answer))
                            sent[0] = True
                        return original_events()
                    task.events = events
                    row = task.trial({'set': 'ABCDE', 'probe': 'A', 'noise_stage': stage,
                                      'noise_filter': 'low', 'noise_loudness': 'quiet'}, 'main', number, 3)
                    self.assertEqual(row['response'], {task.pg.K_LEFT: 'T', task.pg.K_RIGHT: 'F', None: ''}[answer])
                    self.assertEqual(row['correct'], number == 1)
                    self.assertEqual(row['timeout'], answer is None)
                    self.assertGreater(row['noise_stop_command_s'], row['noise_play_command_s'])
                    start = row[stage + '_onset_s']
                    end = row[{'set': 'delay', 'delay': 'probe', 'probe': 'intertrial'}[stage] + '_onset_s']
                    self.assertGreaterEqual(row['noise_play_command_s'], start)
                    self.assertLessEqual(row['noise_stop_command_s'], end)
                    self.assertEqual(row['break_after'], number == 2)
                task.result_file.flush()
                with (task.folder / 'trials.csv').open(encoding='utf-8-sig') as f:
                    saved = list(csv.DictReader(f))
                self.assertEqual(len(saved), 3)
                self.assertEqual(saved[-1]['response_time_ms'], '')
            finally:
                task.result_file.close()
                task.pg.quit()

    def test_escape_persists_incomplete_trial(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg = replace(Settings(), output_dir=folder, seed=42, practice_trials=1,
                          memorize_seconds=.03, delay_seconds=.03, response_timeout_seconds=.08)
            task = Experiment(cfg, 'ABORT')
            original_events = task.events
            def events():
                if task.active_row and task.active_row['delay_onset_s'] != '':
                    task.pg.event.post(task.pg.event.Event(task.pg.KEYDOWN, key=task.pg.K_ESCAPE))
                return original_events()
            task.events = events
            task.message = lambda lines: None
            task.run()
            with (task.folder / 'trials.csv').open(encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['status'], 'aborted')
            self.assertNotEqual(rows[0]['delay_onset_s'], '')
            self.assertEqual(rows[0]['probe_onset_s'], '')
            self.assertEqual(task.metadata['status'], 'aborted')


if __name__ == '__main__':
    unittest.main()
