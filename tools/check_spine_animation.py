"""Original Spine timelines and battle presentation, without game windows."""
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
from battle import Battle
from battle_ui import BattleUI
from csb_render import CocosUI
from spine_renderer import timeline, draw_order, curve_percent, render_pose

DATA = OriginalData(ROOT/'original-1.20.4')


class SpineChecks(unittest.TestCase):
    def test_timeline_interpolation_step_and_short_rotation(self):
        frames = [{'time': 0, 'x': 0}, {'time': 1, 'x': 20}]
        self.assertIsNone(timeline(frames, -.1, ['x'], [0]))
        self.assertEqual([10], timeline(frames, .5, ['x'], [0]))
        frames[0]['curve'] = 'stepped'
        self.assertEqual([0], timeline(frames, .8, ['x'], [0]))
        self.assertAlmostEqual(180, timeline([{'angle': 170}, {'time': 1, 'angle': -170}],
                                            .5, ['angle'], [0], True)[0])
        self.assertAlmostEqual(.5, curve_percent([.25, 0, .75, 1], .5), places=4)

    def test_authored_draw_order_offsets_and_reset(self):
        slots = [{'name': name} for name in 'abcd']
        frames = [{'time': 0, 'offsets': [{'slot': 'b', 'offset': 2}]}, {'time': 1}]
        self.assertEqual(list('acdb'), [s['name'] for s in draw_order(slots, frames, .5)])
        self.assertEqual(slots, draw_order(slots, frames, 1))

    def test_original_stand_attack_and_hit_frames_change_with_fixed_world_scale(self):
        for species in ['100001', '100003', '100021']:
            setup = DATA.pet_image(species)
            for clip in ['stand', 'attack', 'underattack']:
                a, b = [DATA.pet_frame(species, clip, frame, clip == 'stand') for frame in (0, 2)]
                self.assertNotEqual(a.tobytes(), b.tobytes(), (species, clip))
                self.assertEqual(a.info['pixels_per_unit'], b.info['pixels_per_unit'])
                self.assertIn('origin', b.info)
                self.assertGreater(b.width*b.height, 0)
            self.assertGreater(setup.height, 0)

    def make_ui(self):
        state = GameState(DATA.tables, 452)
        pet = copy.deepcopy(state.pets[0])
        pet.talents = []
        enemy = copy.deepcopy(pet)
        enemy.uid = 'enemy-test'
        battle = Battle(DATA.tables, [pet], [enemy], state.rng)
        for u in battle.player+battle.enemy:
            u.hp = u.max_hp = 10000
        app = SimpleNamespace(data=DATA, state=state, cocos_ui=CocosUI(DATA), battle_tips=[])
        return BattleUI(app, battle), battle

    def test_host_size_and_authored_origins(self):
        ui, battle = self.make_ui()
        image = ui.render()
        self.assertEqual((960, 576), image.size)
        self.assertAlmostEqual(200, ui.pet_positions['player'][0], places=3)
        self.assertAlmostEqual(480, ui.pet_positions['player'][1], places=3)
        self.assertAlmostEqual(730, ui.pet_positions['enemy'][0], places=3)
        self.assertAlmostEqual(336, ui.pet_positions['enemy'][1], places=3)
        for rect in ui.hits.values():
            self.assertTrue(0 <= rect[0] <= rect[2] <= 960)

    def test_two_attacks_replay_in_order_and_clicks_cannot_skip_them(self):
        ui, battle = self.make_ui()
        battle._attack(battle.player_active, battle.enemy_active)
        battle._attack(battle.enemy_active, battle.player_active)
        result_hp = [u.hp for u in battle.player+battle.enemy]
        ui._capture_events()
        self.assertEqual('player', ui.anim['side'])
        self.assertEqual(['enemy'], [a['side'] for a in ui.anim_queue])
        self.assertIsNone(ui.click(750, 250))
        ui.advance(13)
        self.assertLess(ui.display_hp[('enemy', battle.enemy_active.pet.uid)], 10000)
        self.assertEqual(10000, ui.display_hp[('player', battle.player_active.pet.uid)])
        ui.advance(13)
        self.assertEqual('enemy', ui.anim['side'])
        ui.advance(26)
        self.assertIsNone(ui.anim)
        self.assertFalse(ui.anim_queue)
        self.assertEqual(result_hp, [u.hp for u in battle.player+battle.enemy])


if __name__ == '__main__':
    unittest.main(verbosity=2)
