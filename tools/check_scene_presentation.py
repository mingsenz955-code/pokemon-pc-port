"""Original MainUI hit targets and hidden-player save repair, without visible windows."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from types import SimpleNamespace
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from csb_render import CocosUI
from game_state import GameState
from original_data import OriginalData
from pc_game import NativeGame
from scene_ui import SceneUI

DATA = OriginalData(ROOT/'original-1.20.4')


class SceneChecks(unittest.TestCase):
    def test_original_main_ui_button_hits_and_page_callbacks(self):
        calls = []
        app = SimpleNamespace(WIDTH=960, HEIGHT=576, cocos_ui=CocosUI(DATA), data=DATA)
        for name in ('save', 'tasks_ui', 'guide_toggle', 'lottery_ui', 'bag_ui', 'pets_ui', 'illustrated_ui', 'achievements_ui', 'treasure_ui'):
            setattr(app, name, lambda name=name: calls.append(name))
        app.guide_shop = lambda kind: calls.append(('shop', kind))
        ui = SceneUI(app)
        image = Image.new('RGBA', (960, 576))
        ui.render(image)
        for name in ('task_Button', 'mainLeft_Button', 'mainRight_Button', 'mainUp_Button', 'save_Button'):
            self.assertIn(name, ui.hits)
        rect = ui.hits['task_Button']
        self.assertTrue(ui.click((rect[0]+rect[2])/2, (rect[1]+rect[3])/2))
        self.assertEqual(['tasks_ui'], calls)
        ui.action('right_left_1_Button')
        ui.action('right_left_4_Button')
        ui.action('up_left_2_Button')
        self.assertEqual(['tasks_ui', 'bag_ui', 'achievements_ui', ('shop', 2)], calls)
        ui.action('uiDisappear_Button')
        ui.render(image)
        self.assertIn('uiDisappear_Button', ui.hits)
        self.assertNotIn('save_Button', ui.hits)
        ui.action('uiDisappear_Button')
        ui.render(image)
        self.assertIn('save_Button', ui.hits)

    def test_repair_does_not_override_new_or_scripted_hidden_states(self):
        app = NativeGame.__new__(NativeGame)
        app.state = GameState(DATA.tables)
        app.map_id, app.player_visible = 101, False
        app.runtime = SimpleNamespace(file='pEvent101001.json', index=5,
                                      sequence=DATA.event('pEvent101001.json'))
        app.state.presentation = {'player_visible': False, 'player_visibility_map': 101}
        app.repair_legacy_player_visibility()
        self.assertFalse(app.player_visible)
        app.state.presentation.pop('player_visibility_map')
        app.repair_legacy_player_visibility()
        self.assertTrue(app.player_visible)
        app.player_visible = False
        app.runtime.sequence = [{'id': 1, 'type': 'spritevisible',
                                 'parameters': {'spritetype': 1, 'visible': 0}}]
        app.repair_legacy_player_visibility()
        self.assertFalse(app.player_visible)

    def test_cloned_legacy_visibility_fixture_renders_player_without_developer_bars(self):
        # This regression is the reported Stata-town save, not an assumption
        # that every current user save must show the player (the prologue can
        # legitimately hide them). Never depend on or mutate a real save.
        from event_runtime import EventRuntime
        original = tempfile.TemporaryDirectory()
        self.addCleanup(original.cleanup)
        source = Path(original.name)/'slot1.json'
        state = GameState(DATA.tables, seed=40)
        state.initialize(1)
        state.map_id, state.x, state.y = 101, 928, 1056
        state.main_task, state.main_state = 1, 4
        state.presentation = {'player_visible': False, 'screen_black': False}
        runtime = EventRuntime(DATA, state)
        runtime.start('pEvent101001.json')
        runtime.index = 5
        runtime.next()
        state.save(source)
        raw = source.read_bytes()
        snapshot = json.loads(raw)
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'slot1.json').write_bytes(raw)
            previous = os.environ.get('POCKET_NATIVE_SAVE_DIR')
            os.environ['POCKET_NATIVE_SAVE_DIR'] = directory
            root = tk.Tk()
            root.withdraw()
            try:
                app = NativeGame(root, DATA)
                self.assertEqual(snapshot['state']['main_task'], app.state.main_task)
                self.assertEqual(snapshot['state']['map_id'], app.map_id)
                self.assertTrue(app.player_visible)
                self.assertIsNotNone(app.player_image(app.face))
                self.assertEqual(['Canvas'], [child.winfo_class() for child in root.winfo_children()
                                              if child.winfo_manager()])
                self.assertEqual((960, 576), (app.WIDTH, app.HEIGHT))
                image = app.make_frame()
                from PIL import ImageChops
                app.player_visible = False
                without_player = app.make_frame()
                app.player_visible = True
                camx, camy = app.camera_origin()
                px, py = app.x*app.SCALE-camx, app.y*app.SCALE-camy
                region = (max(0, int(px-80)), max(0, int(py-120)),
                          min(app.WIDTH, int(px+80)), min(app.HEIGHT, int(py+10)))
                difference = ImageChops.difference(image.convert('RGB'), without_player.convert('RGB'))
                self.assertIsNotNone(difference.crop(region).getbbox(), 'player has no visible scene pixels')
                output = ROOT/'outputs/verification/player-mainui-repair.png'
                output.parent.mkdir(parents=True, exist_ok=True)
                image.save(output)
            finally:
                for job in root.tk.call('after', 'info'):
                    root.after_cancel(job)
                root.destroy()
                if previous is None:
                    os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
                else:
                    os.environ['POCKET_NATIVE_SAVE_DIR'] = previous
        # Never write the source save; this is a read-only clone.
        self.assertEqual(hashlib.sha256(raw).hexdigest(), hashlib.sha256(source.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main(verbosity=2)
