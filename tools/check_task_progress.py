"""Original task counters and the capture-to-story host integration."""
import json
import os
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from game_state import GameState
from original_data import OriginalData
from event_runtime import EventRuntime
from pc_game import NativeGame
from task_progress import TaskProgress

DATA = OriginalData(ROOT/'original-1.20.4')


class TaskChecks(unittest.TestCase):
    def setUp(self):
        self.state = GameState(DATA.tables, 15)
        self.state.initialize(1)
        self.progress = TaskProgress(self.state)

    def test_next_capture_task_is_not_prematurely_complete(self):
        self.state.main_task, self.state.main_state = 5, 4
        self.state.submit_task(5)
        self.assertEqual((6, 3), (self.state.main_task, self.state.main_state))
        self.progress.update('catch', 100079, 1, 101)
        self.assertEqual(3, self.state.main_state)
        self.progress.update('catch', 100079, 1, 102)
        self.assertEqual(4, self.state.main_state)

    def test_talk_task_acceptance_matches_original_override(self):
        self.state.submit_task(1)
        self.assertEqual((2, 4), (self.state.main_task, self.state.main_state))

    def test_map_task_uses_type_seven(self):
        self.state.main_task, self.state.main_state = 14, 3
        self.progress.update('map', 114)
        self.assertEqual(3, self.state.main_state)
        self.progress.update('map', 115)
        self.assertEqual(4, self.state.main_state)

    def test_money_collection_counts_amount_and_can_regress(self):
        self.state.main_task, self.state.main_state = 18, 3
        self.progress.update()
        self.assertEqual(3, self.state.main_state)
        self.state.grant('700001', 1900)
        self.progress.update()
        self.assertEqual(4, self.state.main_state)
        self.state.consume(['700001'], [1])
        self.progress.update()
        self.assertEqual(3, self.state.main_state)

    def test_fight_requires_correct_type_result_and_npc(self):
        self.state.main_task, self.state.main_state = 37, 3
        for parameters in [(2, 0, 6501011, -1), (2, 1, 6501012, -1)]:
            self.progress.update('fight', *parameters)
            self.assertEqual(3, self.state.main_state)
        self.progress.update('fight', 2, 1, 6501011, -1)
        self.assertEqual(4, self.state.main_state)

    def test_branch_requires_every_configured_fight(self):
        self.state.branch_states['6401'] = 3
        self.progress.update('fight', 2, 1, 6502021, -1)
        self.assertEqual(3, self.state.branch_states['6401'])
        self.progress.update('fight', 2, 1, 6502031, -1)
        self.assertEqual(3, self.state.branch_states['6401'])
        self.progress.update('fight', 2, 1, 6502041, -1)
        self.assertEqual(4, self.state.branch_states['6401'])

    def test_script_mtask_flag_submits_current_task(self):
        self.state.main_task, self.state.main_state = 6, 4
        data = SimpleNamespace(event=lambda name: [] if name == 'pEventContents.json' else [
            {'id': 1, 'type': 'submittask', 'parameters': {'mtask': 5}}])
        runtime = EventRuntime(data, self.state)
        runtime.start('test.json')
        runtime.next()
        # Task 7 still waits for its original area event, whose trigger requires state 3.
        self.assertEqual((7, 3), (self.state.main_task, self.state.main_state))
        self.assertIn(6, self.state.completed_main)

    def test_starter_choice_id_is_separate_from_character_initialization(self):
        runtime = EventRuntime(DATA, self.state)
        self.assertTrue(runtime.branch_matches({'initid': 0}))
        self.state.starter_id = 2
        self.assertTrue(runtime.branch_matches({'initid': 2}))
        self.assertEqual(1, self.state.initialization)

    def test_capture_host_notifies_tutorial_and_followup_without_fake_result(self):
        with tempfile.TemporaryDirectory() as folder:
            old = os.environ.get('POCKET_NATIVE_SAVE_DIR')
            os.environ['POCKET_NATIVE_SAVE_DIR'] = folder
            root = tk.Tk()
            try:
                app = NativeGame(root, DATA)
                root.withdraw()
                app.state = self.state
                self.state.main_task, self.state.main_state = 6, 3
                self.state.add_preset(201)
                self.state.events['101004'] = 1
                self.state.inventory['220006'] = 1
                app.runtime = EventRuntime(DATA, self.state)
                app.display_request, app.dialogue, app.pending_wait = None, None, None
                app.load_map(102)
                enemy_id = DATA.tables['VillageMap']['102']['enemyIds'].split(',')[0]
                app.start_battle(enemy_id, 'wild')
                self.assertEqual('pEvent102001.json', app.runtime.file)
                app.battle_ui.selected = {'id': '220006', 'kind': 'ball'}
                app.battle_ui._action('confirm_yes')
                self.assertEqual('caught', app.battle.result)
                self.assertEqual(0, self.state.count('220006'))
                app.finish_battle()
                for _ in range(100):
                    if app.display_request:
                        app.interact()
                    else:
                        app.drive()
                    if not app.runtime.running:
                        break
                self.assertFalse(app.runtime_error, app.runtime_error)
                self.assertEqual(1, self.state.events.get('102001'))
                self.assertEqual(1, self.state.events.get('101005'))
                self.assertEqual((7, 3), (self.state.main_task, self.state.main_state))
                self.assertEqual(2, len(self.state.pets))
            finally:
                root.destroy()
                if old is None:
                    os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
                else:
                    os.environ['POCKET_NATIVE_SAVE_DIR'] = old


if __name__ == '__main__':
    unittest.main(verbosity=2)
