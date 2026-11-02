"""No-window checks for click-to-walk, route rendering and exact NPC arrival."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from check_story_motion import host, move, DATA
from guide import Guide
from pc_game import NativeGame


def navigation_host(walls=()):
    app = host(move(), walls)
    app.runtime.file, app.runtime.sequence, app.runtime.pending = '', [], None
    app.noclip = False
    app.calls = []
    app.interact = lambda npc_id=None: app.calls.append(npc_id)
    app.try_exit = lambda: None
    app.data = DATA
    app.guide = Guide(app)
    return app


def finish(app, limit=300):
    for _ in range(limit):
        if not app.guide.active:
            return
        app.guide.step(.04)
    raise AssertionError('Click route did not terminate')


class ClickChecks(unittest.TestCase):
    def test_clicked_ground_walks_real_route_around_wall(self):
        app = navigation_host({(2, 1)})
        self.assertTrue(app.guide.start_click(224, 96))
        self.assertEqual((96, 96), (app.x, app.y))
        self.assertTrue(app.guide.waypoints)
        self.assertNotIn([160, 96], app.guide.waypoints)
        finish(app)
        self.assertEqual((224, 96), (app.x, app.y))
        self.assertFalse(app.calls)

    def test_click_npc_walks_adjacent_turns_and_talks_once_to_selected_actor(self):
        app = navigation_host()
        app.actors = lambda: [('42', '20001', 352, 96), ('43', '20001', 288, 160)]
        app.guide.start_click(352, 96, '42')
        self.assertFalse(app.calls)
        finish(app)
        self.assertEqual(['42'], app.calls)
        self.assertEqual('standright', app.face)
        self.assertNotEqual((352, 96), (app.x, app.y))
        for _ in range(5):
            app.guide.step(.04)
        self.assertEqual(['42'], app.calls)

    def test_new_click_replaces_route_and_stop_clears_markers(self):
        app = navigation_host()
        app.guide.start_click(480, 96)
        app.guide.step(.04)
        app.guide.start_click(96, 352)
        self.assertEqual((96, 352), (app.guide.target.x, app.guide.target.y))
        finish(app)
        self.assertEqual((96, 352), (app.x, app.y))
        self.assertFalse(app.guide.waypoints)
        app.guide.start_click(352, 352)
        app.guide.stop()
        self.assertFalse(app.guide.waypoints)

    def test_enclosed_npc_never_teleports_or_talks(self):
        app = navigation_host({(4, 3), (3, 4), (5, 4), (4, 5)})
        app.actors = lambda: [('42', '20001', 288, 288)]
        before = (app.x, app.y)
        self.assertFalse(app.guide.start_click(288, 288, '42'))
        self.assertEqual(before, (app.x, app.y))
        self.assertFalse(app.calls)

    def test_moving_npc_is_replanned_and_disappearing_npc_is_not_talked_to(self):
        app = navigation_host()
        actors = [('42', '20001', 352, 96)]
        app.actors = lambda: actors
        app.guide.start_click(352, 96, '42')
        app.guide.step(.04)
        actors[:] = [('42', '20001', 416, 160)]
        finish(app)
        self.assertEqual(['42'], app.calls)
        actors[:] = [('42', '20001', 480, 352)]
        app.guide.start_click(480, 352, '42')
        actors.clear()
        app.guide.step(.04)
        self.assertFalse(app.guide.active)
        self.assertEqual(['42'], app.calls)

    def test_click_conversion_uses_camera_zoom_and_sprite_alpha_hit(self):
        app = navigation_host()
        app.SCALE = .5
        app.camera_origin = lambda: (64, 16)
        app.actor_animation = lambda *args: 'standdown'
        app.scene_sprite = lambda *args: Image.new('RGBA', (40, 60), 'red')
        app.actors = lambda: [('42', '20001', 352, 160)]
        NativeGame.click_walk(app, 112, 49)
        self.assertEqual('42', app.guide.target.npc_id)
        NativeGame.click_walk(app, 160, 160)
        self.assertEqual('point', app.guide.target.kind)
        self.assertEqual((480, 352), (app.guide.target.x, app.guide.target.y))

    def test_route_uses_original_dots_and_endpoint_art_offscreen(self):
        app = navigation_host()
        app.guide.start_click(352, 96)
        app.data, app.SCALE, app.WIDTH, app.HEIGHT, app.scene_animation_time = DATA, .65, 400, 250, .1
        frame = Image.new('RGBA', (400, 250))
        NativeGame.render_world_overlay(app, frame, 0, 0)
        self.assertIsNotNone(frame.getbbox())
        app.guide.stop()
        cleared = Image.new('RGBA', frame.size)
        NativeGame.render_world_overlay(app, cleared, 0, 0)
        self.assertIsNone(cleared.getbbox())

    def test_entering_exit_runs_transition_and_stops_old_map_route(self):
        app = navigation_host()
        def exit_map():
            if app.x >= 224:
                app.map_id = 102
        app.try_exit = exit_map
        app.guide.start_click(224, 96)
        finish(app)
        self.assertEqual(102, app.map_id)
        self.assertFalse(app.guide.active)

    def test_hud_and_dialogue_clicks_do_not_start_movement(self):
        app = navigation_host()
        app.scene_ui = SimpleNamespace(click=lambda *args: True)
        NativeGame.on_click(app, SimpleNamespace(x=10, y=10))
        self.assertFalse(app.guide.active)
        app.scene_ui.click = lambda *args: False
        app.runtime.file = 'dialogue.json'
        NativeGame.on_click(app, SimpleNamespace(x=10, y=10))
        self.assertEqual([None], app.calls)
        self.assertFalse(app.guide.active)

    def test_direction_key_cancels_click_route(self):
        app = navigation_host()
        app.guide.start_click(352, 96)
        NativeGame.key_down(app, SimpleNamespace(keysym='d'))
        self.assertFalse(app.guide.active)
        self.assertFalse(app.guide.waypoints)
        self.assertIn('d', app.keys)

    def test_same_id_chest_does_not_replace_clicked_npc(self):
        app = navigation_host()
        app.actors = lambda: [('42', '30001', 96, 352), ('42', '20001', 352, 96)]
        app.interact = lambda *target: app.calls.append(target)
        app.guide.start_click(352, 96, '42', '20001')
        finish(app)
        self.assertEqual([('42', '20001')], app.calls)

    def test_clicking_original_quest_marker_also_selects_its_npc(self):
        app = navigation_host()
        app.SCALE, app.scene_animation_time = 1, 0
        app.camera_origin = lambda: (0, 0)
        app.actor_animation = lambda *args: 'standdown'
        app.scene_sprite = lambda *args: Image.new('RGBA', (40, 60), 'red')
        app.actors = lambda: [('580101', '20001', 352, 160)]
        app.state.main_task, app.state.main_state = 58, 3
        app.state.branch_states = {k: 5 for k in DATA.tables['BranchTask']}
        app.state.branch_states['1001'] = 3
        NativeGame.click_walk(app, 352, 80)
        self.assertEqual('580101', app.guide.target.npc_id)


if __name__ == '__main__':
    unittest.main(verbosity=2)
