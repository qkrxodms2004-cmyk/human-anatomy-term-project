"""Headless integration checks of real Pygame event handling and CSV persistence."""
import csv
from collections import Counter
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

from sternberg import Experiment, QuitExperiment, Settings, main, prompt_participant


class InterfaceTests(unittest.TestCase):
    def test_id_form_edits_and_persists_confirmed_id(self):
        import pygame as p
        with tempfile.TemporaryDirectory() as folder:
            cfg = replace(Settings(), output_dir=folder)
            events = [
                p.event.Event(p.KEYDOWN, key=p.K_RETURN),  # empty must not confirm
                p.event.Event(p.TEXTINPUT, text='/'),
                p.event.Event(p.KEYDOWN, key=p.K_RETURN),  # invalid must not confirm
                p.event.Event(p.KEYDOWN, key=p.K_BACKSPACE),
                p.event.Event(p.TEXTEDITING, text='P', start=0, length=1),
                p.event.Event(p.KEYDOWN, key=p.K_RETURN),  # composing must not confirm
                p.event.Event(p.TEXTINPUT, text='P001X'),
                p.event.Event(p.KEYDOWN, key=p.K_BACKSPACE),
                p.event.Event(p.KEYDOWN, key=p.K_RETURN),
            ]
            with patch('pygame.event.get', side_effect=[events]):
                participant = prompt_participant(cfg)
            self.assertEqual(participant, 'P001')
            self.assertFalse(any(Path(folder).iterdir()))
            task = Experiment(cfg, participant)
            try:
                self.assertEqual(task.metadata['participant'], 'P001')
                self.assertTrue(task.folder.name.startswith('P001_'))
                import json
                saved = json.loads((task.folder / 'session.json').read_text())
                self.assertEqual(saved['participant'], 'P001')
            finally:
                task.result_file.close()
                p.quit()

    def test_id_form_cancel_exits_before_creating_experiment(self):
        import pygame as p
        for event in (p.event.Event(p.KEYDOWN, key=p.K_ESCAPE), p.event.Event(p.QUIT)):
            with tempfile.TemporaryDirectory() as folder:
                cfg = replace(Settings(), output_dir=folder)
                with patch('sys.argv', ['sternberg.py']), patch('sternberg.load_settings', return_value=cfg), \
                     patch('pygame.event.get', side_effect=[[event]]), patch('sternberg.Experiment') as experiment:
                    main()
                experiment.assert_not_called()
                self.assertFalse(any(Path(folder).iterdir()))

    def test_main_uses_start_screen_id_or_command_line_override(self):
        for args, expected, should_prompt in (([], 'P007', True), (['--participant', 'P008'], 'P008', False)):
            with patch('sys.argv', ['sternberg.py'] + args), \
                 patch('sternberg.prompt_participant', return_value='P007') as prompt, \
                 patch('sternberg.Experiment') as experiment:
                main()
            experiment.assert_called_once()
            self.assertEqual(experiment.call_args.args[1], expected)
            experiment.return_value.run.assert_called_once()
            self.assertEqual(prompt.called, should_prompt)

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
                                      'noise_filter': 'low', 'noise_condition': 'low_' + stage}, 'main', number, 3)
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

    def test_complete_run_balances_conditions_and_keeps_quiet_silent(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg = replace(Settings(), output_dir=folder, seed=17, trials_per_condition=2,
                          calibration_trials=2, practice_trials=1, memorize_seconds=.02,
                          delay_seconds=.02, response_timeout_seconds=.08, intertrial_seconds=.01,
                          break_seconds=.02, post_calibration_wait_seconds=.02)
            task = Experiment(cfg, 'BALANCED', smoke=True)
            original_setup = task.setup
            def setup():
                original_setup()
                task.audio_channel = Mock(wraps=task.audio_channel)
            task.setup = setup
            task.run()
            self.assertEqual(task.metadata['status'], 'completed')
            self.assertEqual(task.metadata['main_trial_count'], 14)
            with (task.folder / 'trials.csv').open(encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
            main = [r for r in rows if r['phase'] == 'main']
            counts = Counter(r['noise_condition'] for r in main)
            self.assertEqual(len(counts), 7)
            self.assertEqual(set(counts.values()), {2})
            self.assertEqual(task.audio_channel.play.call_count, 12)
            for row in main:
                self.assertEqual(row['status'], 'completed')
                if row['noise_condition'] == 'quiet':
                    self.assertEqual(row['noise_stage'], 'none')
                    self.assertEqual(row['noise_filter'], 'none')
                    self.assertEqual(row['noise_play_command_s'], '')
                    self.assertEqual(row['noise_stop_command_s'], '')
                    self.assertEqual(row['noise_target_rms'], '0')
                    self.assertEqual(row['noise_command_duration_ms'], '0')
                    self.assertEqual(row['noise_min_hz'], '')
                else:
                    self.assertGreater(float(row['noise_command_duration_ms']), 0)
                    self.assertEqual(float(row['noise_min_hz']), getattr(cfg, row['noise_filter'] + '_min_hz'))
                    self.assertEqual(float(row['noise_max_hz']), getattr(cfg, row['noise_filter'] + '_max_hz'))
            self.assertEqual([r['trial'] for r in main if r['break_after'] == 'True'], ['7'])
            self.assertEqual(task.metadata['calibration_valid_responses'], 2)
            purposes = Counter(w['purpose'] for w in task.metadata['waits'])
            self.assertEqual(purposes['break'], 1)
            self.assertEqual(purposes['post_calibration'], 1)

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
