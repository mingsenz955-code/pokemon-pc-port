"""PR 9 follow-up: real repeated rounds, lead selection and task navigation."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from check_click_navigation import navigation_host, finish, DATA
import check_spine_animation as spine_checks
from guide import GuideTarget, GuideResolver
from game_state import GameState
from csb_render import CocosUI
from pc_game import NativeGame


class ReviewChecks(unittest.TestCase):
    def test_consecutive_real_rounds_replay_even_when_event_list_length_is_equal(self):
        ui, battle = spine_checks.SpineChecks().make_ui()
        battle._enemy_action = lambda: {'type': 'attack'}
        for _ in range(3):
            ui._action('attack_Button')
            self.assertIsNotNone(ui.anim)
            self.assertEqual(2, len([ui.anim, *ui.anim_queue]))
            first = ui.anim
            ui.advance(52)
            self.assertIsNone(ui.anim)
            self.assertFalse(ui.anim_queue)
            ui._capture_events()
            self.assertIsNone(ui.anim, 'same events replayed twice')
            self.assertGreater(first['amount'], 0)

    def test_player_bar_reads_the_same_hp_snapshot_as_player_text(self):
        ui, battle = spine_checks.SpineChecks().make_ui()
        unit = battle.player_active
        unit.hp, unit.max_hp = 100, 1000
        ui.display_hp[('player', unit.pet.uid)] = 250
        ui._hud_rects = {'mine': {'mine/hp_LoadingBar': (0, 0, 100, 10)}}
        frame = Image.new('RGBA', (110, 15))
        ui._draw_bars(ImageDraw.Draw(frame))
        self.assertNotEqual((20, 22, 24), frame.getpixel((20, 5))[:3])
        self.assertEqual((20, 22, 24), frame.getpixel((50, 5))[:3])

    def test_elapsed_time_consumes_queue_across_action_boundaries(self):
        ui, battle = spine_checks.SpineChecks().make_ui()
        battle._attack(battle.player_active, battle.enemy_active)
        battle._attack(battle.enemy_active, battle.player_active)
        ui._capture_events()
        ui.advance(seconds=.01)
        self.assertAlmostEqual(.25, ui.anim['age'])
        ui.advance(seconds=1.23)
        self.assertEqual('enemy', ui.anim['side'])
        self.assertAlmostEqual(5, ui.anim['age'])
        ui.advance(seconds=1)
        self.assertIsNone(ui.anim)

    def start_battle(self, selected, dead=()):
        state = GameState(DATA.tables, 77)
        state.active_pet = selected
        for index in dead:
            state.pets[index].hp = 0
        order = [p.uid for p in state.pets]
        app = SimpleNamespace(battle=None, data=DATA, state=state, cocos_ui=CocosUI(DATA), keys=set())
        NativeGame.start_battle(app, 1002011)
        self.assertEqual(order, [p.uid for p in state.pets])
        self.assertEqual(order, [u.pet.uid for u in app.battle.player])
        self.assertIn(app.battle.player_active.name, app.battle.messages[1])
        self.assertFalse(app.battle.force_switch)
        return app.battle

    def test_host_uses_selected_opening_pet_without_reordering_party(self):
        self.assertEqual(1, self.start_battle(1).player_index)

    def test_dead_selected_lead_uses_living_pet_before_opening(self):
        self.assertEqual(1, self.start_battle(0, dead=(0,)).player_index)

    def test_task_navigation_avoids_npc_instead_of_only_click_navigation(self):
        app = navigation_host()
        app.actors = lambda: [('42', '20001', 352, 96), ('43', '20001', 224, 96)]
        app.guide.start(GuideTarget('npc', 'quest NPC', 101, 352, 96, npc_id='42'))
        app.guide.step(.04)
        self.assertNotIn((224, 96), [tuple(p) for p in app.guide.waypoints])
        finish(app)
        self.assertEqual(['42'], app.calls)

    def test_task_target_does_not_follow_chest_with_the_same_object_id(self):
        app = navigation_host()
        app.actors = lambda: [('42', '30001', 224, 96), ('42', '20001', 416, 96)]
        calls = []
        app.interact = lambda npc_id, sprite_id=None: calls.append((npc_id, sprite_id))
        app.guide.start(GuideTarget('npc', 'quest NPC', 101, 416, 96, npc_id='42'))
        finish(app)
        self.assertEqual([('42', '20001')], calls)
        self.assertEqual(416, app.guide.target.x)

    def test_task_route_replans_when_an_actor_steps_onto_next_tile(self):
        app = navigation_host()
        actors = [('42', '20001', 480, 96)]
        app.actors = lambda: actors
        app.guide.start(GuideTarget('npc', 'quest NPC', 101, 480, 96, npc_id='42'))
        app.guide.step(.04)
        actors.append(('43', '20001', *app.guide.waypoints[0]))
        occupied = actors[-1][2:]
        app.guide.step(.04)
        self.assertNotIn(occupied, [tuple(p) for p in app.guide.waypoints])
        finish(app)
        self.assertEqual(['42'], app.calls)

    def test_branch_phase_change_refreshes_selected_branch_not_main_task(self):
        app = navigation_host()
        app.state.branch_states['1'] = 3
        app.guide.resolver = SimpleNamespace(tables={'BranchTask': {'1': {}}},
            from_task=lambda category, key, row, status: GuideTarget(
                'npc', 'submit', 101, 416, 96, category, key, npc_id='43'))
        app.actors = lambda: [('42', '20001', 352, 96), ('43', '20001', 416, 96)]
        app.guide.start(GuideTarget('npc', 'objective', 101, 352, 96, 'branch', '1', npc_id='42'))
        app.state.branch_states['1'] = 4
        # Nonempty row, like the real BranchTask table.
        app.guide.resolver.tables['BranchTask']['1'] = {'name': 'branch'}
        finish(app)
        self.assertEqual(['43'], app.calls)
        self.assertEqual('branch', app.guide.target.task_kind)

    def test_comma_separated_submit_npcs_resolve_to_actual_placement(self):
        state = GameState(DATA.tables, 1)
        resolver = GuideResolver(DATA, state)
        for table, key in [('MainTask', '33'), ('MainTask', '85'), ('BranchTask', '6201')]:
            row = DATA.tables[table][key]
            target = resolver.from_task('main' if table == 'MainTask' else 'branch', key, row, 4)
            self.assertIsNotNone(target)
            self.assertIn(target.npc_id, row['submitNpcs'].split(','))
            self.assertEqual('npc', target.kind)


if __name__ == '__main__':
    unittest.main(verbosity=2)
