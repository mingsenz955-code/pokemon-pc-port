"""Original NPC marker rules and offscreen compositing; no game windows."""
import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from game_state import GameState
from task_icons import TaskIcons, main_icon
from branch_tasks import BranchTasks
from pc_game import NativeGame

DATA = OriginalData(ROOT/'original-1.20.4')


class IconChecks(unittest.TestCase):
    def setUp(self):
        self.state = GameState(copy.deepcopy(DATA.tables), 92)
        self.state.main_task, self.state.main_state = 0, 5
        self.state.branch_states = {k: 5 for k in DATA.tables['BranchTask']}
        self.icons = TaskIcons(self.state)

    def test_branch_available_progress_complete_and_done_use_original_assets(self):
        self.state.main_task = 58
        self.state.main_state = 3
        self.state.branch_states['1001'] = 2
        self.assertEqual(22, self.icons.for_npc(580101))
        self.state.branch_states['1001'] = 3
        self.assertEqual(23, self.icons.for_npc(580101))
        self.assertEqual(29, self.icons.for_npc(40608))
        self.state.branch_states['1001'] = 4
        self.assertEqual(24, self.icons.for_npc(580101))
        self.assertEqual(0, self.icons.for_npc(40608))
        self.state.branch_states['1001'] = 5
        self.assertEqual(0, self.icons.for_npc(580101))
        for key in (12, 13, 14, 19, 22, 23, 24, 29):
            self.assertIsNotNone(DATA.image(f'TaskIcon/taskIcon{key}.png').getbbox())

    def test_locked_branch_and_ordinary_unread_talk_do_not_get_exclamation(self):
        self.state.main_task, self.state.main_state = 1, 3
        self.state.branch_states['1001'] = 2
        self.assertEqual(0, self.icons.for_npc(580101))
        self.assertEqual(0, self.icons.for_npc(999999))

    def test_main_target_precedes_main_giver_and_branch_icons(self):
        row = self.state.tables['MainTask']['1']
        row.update(dispatchNpcs='42', submitNpcs='42', targetNpcs='42')
        branch = self.state.tables['BranchTask']['1001']
        branch.update(dispatchNpcs='42', submitNpcs='42', conditions_mtask='0', conditions_btask='0')
        self.state.main_task = 1
        self.state.branch_states['1001'] = 2
        for status, expected in [(2, 12), (3, 19), (4, 14)]:
            self.state.main_state = status
            self.assertEqual(expected, self.icons.for_npc(42))
            self.assertEqual(expected, main_icon(self.state, 42))
            self.assertIsNone(BranchTasks(self.state).for_npc(42))

    def test_native_bob_cycle_is_four_pixels_over_point_four_seconds(self):
        for time, expected in [(0, 0), (.1, 2), (.2, 4), (.3, 2), (.4, 0)]:
            self.assertAlmostEqual(expected, TaskIcons.bob(time))

    def test_offscreen_overlay_follows_actor_and_skips_same_id_chest(self):
        self.state.main_task, self.state.main_state = 58, 3
        self.state.branch_states['1001'] = 3
        app = SimpleNamespace(booting=False, state=self.state, data=DATA,
                              SCALE=.65, scene_animation_time=.1)
        frame = Image.new('RGBA', (240, 200))
        sprite = Image.new('RGBA', (60, 90))
        NativeGame.render_actor_overlay(app, frame, '580101', '20001', 100, 150, sprite, (30, 90))
        self.assertIsNotNone(frame.getbbox())
        self.assertLess(frame.getbbox()[3], 150)
        chest = Image.new('RGBA', frame.size)
        NativeGame.render_actor_overlay(app, chest, '580101', '30001', 100, 150, sprite, (30, 90))
        self.assertIsNone(chest.getbbox())


if __name__ == '__main__':
    unittest.main(verbosity=2)
