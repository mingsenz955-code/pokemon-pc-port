"""Button-started task route and the original lab/town/home transitions.

Generated saves reproduce the reported task-4 location. The navigation-only
post-rival fixture explicitly marks that plot completed; it is not a claim of
having won the real battle. A separate fixture checks that the original rival
plot intercepts the route. No player save is written or visible game observed.
"""
import os
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from game_state import GameState
from guide import GuideTarget
from pc_game import NativeGame
from task_guide import TaskGuide

DATA = OriginalData(ROOT/'original-1.20.4')


class HomeGuidance(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.previous = os.environ.get('POCKET_NATIVE_SAVE_DIR')
        os.environ['POCKET_NATIVE_SAVE_DIR'] = self.folder.name
        state = GameState(DATA.tables, 481)
        state.initialize(1)
        state.add_preset(1)
        state.starter_id = 1
        state.map_id, state.x, state.y = 5801, 660.2835921351, 528.9170980079
        state.main_task, state.main_state = 4, 4
        state.presentation = {'player_visible': True, 'sprite_collision_version': 2}
        state.save(Path(self.folder.name)/'slot1.json')
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = NativeGame(self.root, DATA)

    def tearDown(self):
        for job in self.root.tk.call('after', 'info'):
            self.root.after_cancel(job)
        self.root.destroy()
        self.folder.cleanup()
        if self.previous is None:
            os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
        else:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = self.previous

    def click_guide(self):
        self.app.make_frame()
        r = self.app.scene_ui.hits['mainUp_Button']
        self.app.on_click(SimpleNamespace(x=(r[0]+r[2])/2, y=(r[1]+r[3])/2))

    def travel(self):
        app = self.app
        maps = [app.map_id]
        for _ in range(700):
            # Simulated travel does not wait wall-clock exit debounces.
            app.exit_time = 0
            app.guide.step(.04)
            if app.map_id != maps[-1]:
                maps.append(app.map_id)
                self.assertLess(len(maps), 5, 'route bounced through the previous exit')
            if app.runtime.running or not app.guide.active:
                return maps
        self.fail(f'route stalled: {app.map_id}, {app.guide.message}')

    def test_button_starts_current_task_and_second_press_stops(self):
        app = self.app
        self.assertIsNone(TaskGuide(app).point())
        self.assertFalse(app.guide.active)
        self.click_guide()
        self.assertTrue(app.guide.active)
        self.assertEqual(('4', 5807, '580701'),
                         (app.guide.target.task_id, app.guide.target.map_id, app.guide.target.npc_id))
        app.guide.step(.04)
        self.assertIsNotNone(TaskGuide(app).point())
        self.click_guide()
        self.assertFalse(app.guide.active)
        self.assertIsNone(TaskGuide(app).point())

    def test_original_rival_plot_interrupts_without_skipping_battle(self):
        self.click_guide()
        self.assertEqual([5801, 101], self.travel())
        self.assertEqual('pEvent101002.json', self.app.runtime.file)
        self.assertIsNone(self.app.battle)
        self.assertEqual(4, self.app.state.main_task)

    def test_post_rival_route_enters_home_and_starts_real_mother_dialogue(self):
        self.app.state.events['101002'] = 1
        self.click_guide()
        self.assertEqual([5801, 101, 5807], self.travel())
        self.assertEqual('pEvent5807003.json', self.app.runtime.file)
        self.assertFalse(self.app.guide.active)
        self.assertIsNone(TaskGuide(self.app).point())

    def test_home_door_is_not_covered_by_shifted_building_mask(self):
        world = DATA.load_map(101)
        self.assertFalse(world.blocked(96, 1248))
        self.assertTrue(world.sprite_blocked(224, 1248))
        home = next(o for o in world.objects if o.get('gid') and o['group'] == 'spriteTileLayer'
                    and world.tile_properties(int(o['gid'])).get('spriteId') == '50083')
        y = next(y for x, y, image in world.scenery() if x == float(home['x'])+32 and y == float(home['y'])-32)
        self.assertEqual(1248, y)

    def test_arrow_follows_next_route_turn_not_the_remote_house_coordinates(self):
        app = self.app
        app.guide.active = True
        app.guide.target = GuideTarget('npc', 'home', 5807, 608, 768)
        app.guide.waypoints = [[app.x, app.y+64], [app.x, app.y+128], [app.x+64, app.y+128]]
        self.assertEqual([app.x, app.y+128], TaskGuide(app).point())
        app.guide.stop()
        self.assertIsNone(TaskGuide(app).point())

    def test_old_broken_obstacles_keep_their_removed_state_after_origin_fix(self):
        world = DATA.load_map(202)
        obj = next(o for o in world.objects if o.get('group') == 'spriteTileLayer' and o.get('gid')
                   and int(world.tile_properties(int(o['gid'])).get('obsType', 0)))
        kind = int(world.tile_properties(int(obj['gid']))['obsType'])
        tx, old_y = int(float(obj['x'])//64), int(float(obj['y'])//64)
        state = GameState(DATA.tables, 1)
        state.removed_obstacles = [[202, tx, old_y, kind]]
        NativeGame.repair_legacy_obstacle_coordinates(self.app, state)
        new_y = int((float(obj['y'])-32)//64)
        self.assertEqual([[202, tx, new_y, kind]], state.removed_obstacles)
        self.assertEqual(kind, world.remove_obstacle(tx, new_y))
        snapshot = state.payload()
        NativeGame.repair_legacy_obstacle_coordinates(self.app, state)
        self.assertEqual(snapshot, state.payload())


if __name__ == '__main__':
    unittest.main(verbosity=2)
