"""No-window checks of native screenmove sequencing and saved interpolation."""
import json
import math
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from event_runtime import EventRuntime
from game_state import GameState
from original_data import OriginalData
from pc_game import NativeGame

DATA = OriginalData(ROOT/'original-1.20.4')


def host(parameters):
    app = NativeGame.__new__(NativeGame)
    app.state = GameState(DATA.tables, seed=8)
    script = [{'id': 1, 'type': 'screenmove', 'parameters': parameters},
              {'id': 2, 'type': 'talk', 'text': '镜头完成后的下一句'}]
    data = SimpleNamespace(tables=DATA.tables,
                           event=lambda name: [] if name == 'pEventContents.json' else script)
    app.data = data
    app.runtime = EventRuntime(data, app.state)
    app.runtime.start('camera-check.json')
    app.map = SimpleNamespace(tw=64, th=64)
    app.background = SimpleNamespace(width=4096, height=4096)
    app.x, app.y = 1504, 1504
    app.camera_focus, app.camera_action = None, None
    app.display_request, app.pending_wait, app.dialogue = None, None, None
    app.runtime_error, app.battle, app.ui_open, app.wait_until = '', None, False, 0
    app.booting, app.ui_window, app.map_id = False, None, 101
    app.face, app.player_visible, app.main_ui_visible = 'standdown', True, True
    app.teach_nodes, app.keys = [], set()
    app.encounter_distance, app.encounter_threshold = 0, 0
    app.ui_info = None
    app.audio = SimpleNamespace(effect=lambda *args: None)
    app.guide = SimpleNamespace(rebind=lambda state: None)
    return app


class CameraChecks(unittest.TestCase):
    def test_screen_waits_for_native_fade_before_next_dialogue(self):
        from unittest.mock import patch
        app = host({})
        app.runtime.sequence[0].update(type='screen', parameters={'type': 1})
        app.screen_black = True
        with patch('pc_game.time.monotonic', return_value=100):
            app.drive()
        self.assertEqual(100.5, app.screen_fade_until)
        self.assertEqual('screen', app.runtime.pending.kind)
        with patch('pc_game.time.monotonic', return_value=100.25):
            app.drive()
        self.assertIsNone(app.display_request)
        with patch('pc_game.time.monotonic', return_value=100.5):
            app.drive()
        self.assertFalse(app.screen_black)
        self.assertEqual('talk', app.display_request.kind)

    def test_move_delay_then_original_script_callback(self):
        app = host({'x': 29, 'y': 22, 'speedscale': 2, 'stop': 1})
        app.drive()
        action = app.camera_action
        self.assertEqual('screenmove', app.runtime.pending.kind)
        self.assertIsNone(app.display_request)
        self.assertEqual([1888, 1376], action['target'])
        self.assertAlmostEqual(math.dist(action['start'], action['target'])/64*.1/2,
                               action['duration'])
        app.advance_camera(action['duration']/2)
        self.assertEqual([(a+b)/2 for a, b in zip(action['start'], action['target'])], app.camera_focus)
        app.drive()
        self.assertIsNone(app.display_request)
        app.advance_camera(action['duration']/2+.49)
        self.assertIsNotNone(app.camera_action)
        app.advance_camera(.02)
        self.assertIsNone(app.camera_action)
        self.assertEqual(1, app.runtime.index)
        app.drive()
        self.assertEqual('talk', app.display_request.kind)
        app.advance_camera(100)
        self.assertEqual('talk', app.runtime.pending.kind)

    def test_zero_speed_has_no_delay(self):
        app = host({'x': 29, 'y': 22, 'speedscale': 0, 'stop': 1})
        app.drive()
        self.assertIsNone(app.camera_action)
        self.assertEqual([1888, 1376], app.camera_focus)
        self.assertEqual('talk', app.display_request.kind)

    def test_missing_speed_uses_original_default_one(self):
        app = host({'x': 29, 'y': 22, 'stop': 1})
        app.drive()
        action = app.camera_action
        self.assertAlmostEqual(math.dist(action['start'], action['target'])/64*.1, action['duration'])

    def test_follow_player_returns_after_callback(self):
        app = host({'x': -1, 'y': -1, 'speedscale': 1, 'stop': 0})
        app.camera_focus = [1888, 1376]
        app.drive()
        action = app.camera_action
        self.assertEqual([1504, 1440], action['target'])
        app.advance_camera(action['duration']+.5)
        self.assertIsNone(app.camera_focus)
        self.assertEqual((1504, 1440), app.follow_focus())

    def test_json_snapshot_resumes_remaining_time_once(self):
        app = host({'x': 29, 'y': 22, 'speedscale': 1, 'stop': 1})
        app.drive()
        app.advance_camera(app.camera_action['duration']/2)
        app.runtime.persist()
        snapshot = json.loads(json.dumps({'action': app.camera_action, 'focus': app.camera_focus,
                                         'runtime': app.state.pending_runtime}))
        other = host({'x': 29, 'y': 22, 'speedscale': 1, 'stop': 1})
        other.camera_action, other.camera_focus = snapshot['action'], snapshot['focus']
        other.runtime = EventRuntime(other.runtime.data, other.state)
        other.runtime.restore(snapshot['runtime'])
        elapsed = other.camera_action['elapsed']
        other.drive()
        self.assertEqual(elapsed, other.camera_action['elapsed'])
        other.advance_camera(other.camera_action['duration']-elapsed+.5)
        other.drive()
        self.assertEqual('talk', other.display_request.kind)
        self.assertIsNone(other.camera_action)

    def test_small_map_is_clamped(self):
        app = host({'x': 100, 'y': 100, 'speedscale': 1, 'stop': 1})
        app.background = SimpleNamespace(width=300, height=200)
        app.drive()
        self.assertEqual((0, 0), app.camera_origin())
        self.assertEqual(0, app.camera_action['duration'])

    def test_native_save_restore_preserves_in_progress_camera(self):
        with tempfile.TemporaryDirectory() as directory:
            app = host({'x': 29, 'y': 22, 'speedscale': 1, 'stop': 1})
            app.save_path = Path(directory)/'slot1.json'
            app.drive()
            app.advance_camera(app.camera_action['duration']/2)
            app.save()
            expected = json.loads(json.dumps(app.camera_action))
            # Isolate rendering/map loading only; use the real host save,
            # GameState deserializer and EventRuntime restoration.
            app.load_map = lambda mid, x, y: None
            app.camera_action, app.camera_focus = None, None
            app.restore()
            self.assertEqual(expected, app.camera_action)
            self.assertEqual('screenmove', app.runtime.pending.kind)
            self.assertIsNone(app.display_request)
            app.advance_camera(expected['duration']-expected['elapsed']+.5)
            app.drive()
            self.assertEqual('talk', app.display_request.kind)


if __name__ == '__main__':
    unittest.main(verbosity=2)
