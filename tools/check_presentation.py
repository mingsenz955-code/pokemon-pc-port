"""Native host regressions for user-reported clipping, invisible player and saves."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import tkinter as tk
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from pc_game import NativeGame
from event_runtime import Request
from game_state import GameState


class PresentationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = OriginalData(ROOT/'original-1.20.4')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = os.environ.get('POCKET_NATIVE_SAVE_DIR')
        os.environ['POCKET_NATIVE_SAVE_DIR'] = self.temp.name
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()
        self.temp.cleanup()
        if self.previous is None:
            os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
        else:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = self.previous

    def test_opening_uses_original_aside_and_reveals_map_after_three_lines(self):
        app = NativeGame(self.root, self.data)
        self.assertEqual(app.display_request.kind, 'aside')
        self.assertTrue(app.screen_black)
        folder = ROOT/'outputs/verification/presentation'
        folder.mkdir(parents=True, exist_ok=True)
        app.make_frame().save(folder/'opening-aside.png')
        self.assertEqual(app.cocos_ui.layout('AsideUI')['tree']['children'][1]['h_align'], 1)
        for _ in range(3):
            app.interact()
        self.assertFalse(app.screen_black)
        self.assertEqual(app.display_request.kind, 'airtalk')
        app.make_frame().save(folder/'opening-visible.png')

    def test_exit_does_not_push_player_outside_room(self):
        app = NativeGame(self.root, self.data)
        app.request_map(580101)
        self.assertEqual((app.x, app.y), (1312, 1024))
        self.assertLess(app.x, app.map.width*app.map.tw)
        self.assertIsNotNone(app.player_image(app.face))
        self.assertEqual(app.face, 'standleft')

    def test_legacy_outside_position_is_repaired_without_touching_source(self):
        state = GameState(self.data.tables)
        state.map_id, state.x, state.y = 5801, 1376, 1024
        state.pending_runtime = None
        state.save(Path(self.temp.name)/'slot1.json')
        app = NativeGame(self.root, self.data)
        self.assertEqual((app.map_id, app.x, app.y), (5801, 1312, 1024))
        self.assertIsNotNone(app.player_image(app.face))
        original = json.loads((Path(self.temp.name)/'slot1.json').read_text('utf-8'))
        self.assertEqual(original['state']['x'], 1376)

    def test_automatic_resume_and_previous_progress_backup(self):
        app = NativeGame(self.root, self.data)
        for _ in range(2):
            app.interact()
        step = app.runtime.index
        app.autosave()
        app.interact()
        app.autosave()
        backups = list((Path(self.temp.name)/'backups').glob('slot1-*.json'))
        self.assertTrue(backups)
        self.assertTrue(any(json.loads(p.read_text('utf-8'))['state']['pending_runtime']['index'] == step
                            for p in backups))
        self.root.destroy()
        self.root = tk.Tk()
        self.root.withdraw()
        restored = NativeGame(self.root, self.data)
        self.assertEqual(restored.runtime.index, app.runtime.index)
        self.assertEqual(restored.dialogue, app.dialogue)

    def test_corrupt_primary_uses_backup_without_destroying_either(self):
        state = GameState(self.data.tables)
        state.map_id, state.x, state.y = 5801, 500, 600
        path = Path(self.temp.name)/'slot1.json'
        state.save(path)
        state.x = 600
        state.save(path)
        path.write_text('{broken', encoding='utf-8')
        app = NativeGame(self.root, self.data)
        self.assertEqual(app.x, 500)
        self.assertEqual(path.read_text('utf-8'), '{broken')

    def test_camera_waits_for_interpolation_and_completion_delay(self):
        app = NativeGame(self.root, self.data)
        app.camera_focus = (1000, 1000)
        request = Request('screenmove', 'test', 1, {'parameters': {'x': 20, 'y': 4, 'stop': 1, 'speedscale': 1}})
        app.runtime.pending = request
        app.apply_visual(request)
        action = app.camera_action
        self.assertIsNotNone(action)
        start = list(app.camera_focus)
        app.advance_camera(action['duration']/2)
        self.assertNotEqual(start, app.camera_focus)
        self.assertIs(app.runtime.pending, request)
        app.advance_camera(action['duration']/2+.49)
        self.assertIs(app.runtime.pending, request)
        app.advance_camera(.02)
        self.assertIsNone(app.camera_action)
        self.assertIsNone(app.runtime.pending)

    def test_camera_mid_move_save_resumes_remaining_action(self):
        app = NativeGame(self.root, self.data)
        # Reach the actual first screenmove request after the crowd dialogue.
        for _ in range(4):
            app.interact()
        self.assertEqual(app.runtime.pending.kind, 'screenmove')
        self.assertIsNotNone(app.camera_action)
        app.advance_camera(.2)
        app.autosave()
        elapsed = app.camera_action['elapsed']
        self.root.destroy()
        self.root = tk.Tk()
        self.root.withdraw()
        restored = NativeGame(self.root, self.data)
        self.assertAlmostEqual(restored.camera_action['elapsed'], elapsed)
        self.assertEqual(restored.runtime.pending.kind, 'screenmove')


if __name__ == '__main__':
    unittest.main(verbosity=2)
