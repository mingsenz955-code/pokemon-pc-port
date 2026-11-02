"""No-window checks of story walking, relative spaces, callbacks and saves."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from event_runtime import EventRuntime, PendingMechanic
from game_state import GameState
from original_data import OriginalData
from pc_game import NativeGame
from story_motion import StoryMotion, destination, shortest_path

DATA = OriginalData(ROOT/'original-1.20.4')


def host(parameters, walls=()):
    app = NativeGame.__new__(NativeGame)
    script = [{'id': 1, 'type': 'toplace', 'parameters': parameters},
              {'id': 2, 'type': 'talk', 'text': '全部人物到达后的下一句'}]
    app.data = SimpleNamespace(tables=DATA.tables,
        event=lambda name: [] if name == 'pEventContents.json' else script)
    app.state = GameState(DATA.tables, seed=5)
    app.runtime = EventRuntime(app.data, app.state)
    app.runtime.start('motion-check.json')
    app.map_id, app.x, app.y = 101, 96, 96
    app.map = SimpleNamespace(tw=64, th=64, width=10, height=10, objects=[],
        info={'mapType': '2'}, terrain_at=lambda x, y: 0,
        blocked=lambda x, y, mounts=None: (int(x//64), int(y//64)) in walls)
    app.actors = lambda: []
    app.face = 'standdown'
    app.state.temp_npcs['1'] = {'map': 101, 'visible': 1, 'spriteid': 10001, 'x': 96, 'y': 160}
    app.story_motion = StoryMotion(app)
    app.booting, app.battle, app.camera_action, app.camera_focus = False, None, None, None
    app.runtime_error, app.wait_until, app.ui_open, app.ui_window = '', 0, False, None
    app.display_request, app.pending_wait, app.dialogue = None, None, None
    app.player_visible, app.main_ui_visible = True, True
    app.teach_nodes, app.keys = [], set()
    app.encounter_distance, app.encounter_threshold = 0, 0
    app.guide = SimpleNamespace(rebind=lambda state: None)
    return app


def move(kind=1, identifier=0, x=3, y=1, speed=1, **extra):
    return dict(spritetype=kind, spriteid=identifier, x=x, y=y, speedscale=speed, **extra)


class StoryChecks(unittest.TestCase):
    def test_zero_speed_is_original_top_origin_position(self):
        app = host(move(x=4, y=6, speed=0, face=3))
        app.drive()
        self.assertEqual((288, 416, 'standleft'), (app.x, app.y, app.face))
        self.assertFalse(app.story_motion.actions)
        self.assertEqual('talk', app.display_request.kind)

    def test_nonzero_speed_walks_and_does_not_resume_early(self):
        app = host(move())
        app.drive()
        self.assertEqual((96, 96), (app.x, app.y))
        app.story_motion.advance(.1)
        self.assertAlmostEqual(128, app.x)
        self.assertEqual('walkright', app.story_motion.animation(1, 0, app.face))
        app.drive()
        self.assertIsNone(app.display_request)
        app.story_motion.advance(.31)
        self.assertEqual((224, 96), (app.x, app.y))
        app.drive()
        self.assertEqual('talk', app.display_request.kind)
        app.story_motion.advance(100)
        self.assertEqual('talk', app.runtime.pending.kind)

    def test_all_parallel_actors_must_arrive(self):
        app = host([move(x=2), move(7, 1, x=4, y=2, face=1)])
        app.drive()
        app.story_motion.advance(.21)
        self.assertEqual((160, 96), (app.x, app.y))
        self.assertEqual(1, len(app.story_motion.actions))
        app.drive()
        self.assertIsNone(app.display_request)
        app.story_motion.advance(.4)
        self.assertEqual((288, 160), tuple(app.story_motion.position(7, 1)))
        self.assertEqual('standup', app.story_motion.animation(7, 1, 'standdown'))
        app.drive()
        self.assertEqual('talk', app.display_request.kind)

    def test_relative_coordinates_reference_player_not_moving_actor(self):
        target = destination(move(7, 1, x=-1, y=2, pspace=1), (352, 480), 'standup', (64, 64))
        self.assertEqual([288, 608], target)

    def test_facing_relative_space_matches_original_jump_table(self):
        expected = {1: [480, 672], 2: [224, 288], 3: [544, 352], 4: [544, 608]}
        for face, point in expected.items():
            self.assertEqual(point, destination(move(x=2, y=3, pspace=2, face=face),
                                               (352, 480), 'standdown', (64, 64)))
        self.assertEqual(expected[3], destination(move(x=2, y=3, pspace=2, face=0),
                                                 (352, 480), 'standleft', (64, 64)))

    def test_path_walks_around_wall_instead_of_crossing_it(self):
        app = host(move(), walls={(2, 1)})
        app.drive()
        path = copy.deepcopy(app.story_motion.actions[0]['path'])
        self.assertGreater(len(path), 2)
        self.assertNotIn([160, 96], path)
        for _ in range(20):
            app.story_motion.advance(.05)
            self.assertNotEqual((2, 1), (int(app.x//64), int(app.y//64)))
        self.assertEqual((224, 96), (app.x, app.y))

    def test_unreachable_target_walks_to_original_closest_candidate(self):
        app = host(move(), walls={(3, 1)})
        app.drive()
        self.assertFalse(app.runtime_error)
        self.assertEqual((96, 96), (app.x, app.y))
        self.assertEqual('toplace', app.runtime.pending.kind)
        app.story_motion.advance(10)
        self.assertEqual((160, 96), (app.x, app.y))
        app.drive()
        self.assertEqual('talk', app.display_request.kind)

    def test_completely_enclosed_actor_completes_without_teleport(self):
        app = host(move(), walls={(1, 0), (0, 1), (2, 1), (1, 2)})
        app.drive()
        self.assertEqual((96, 96), (app.x, app.y))
        self.assertFalse(app.story_motion.actions)
        self.assertEqual('talk', app.display_request.kind)

    def test_bulk_movement_notifies_task_for_intermediate_area(self):
        app = host(move())
        app.map.objects = [{'group': 'eventLayer', 'name': '10101',
                            'x': 128, 'y': 64, 'width': 64, 'height': 64}]
        app.drive()
        self.assertEqual(3, app.state.main_state)
        app.story_motion.advance(.41)
        self.assertEqual((224, 96), (app.x, app.y))
        self.assertEqual(4, app.state.main_state)
        self.assertEqual([1], app.state.task_counts['main:1'])
        self.assertEqual([], app.runtime.queue)

    def test_outside_goal_uses_valid_edge_candidate(self):
        app = host(move(x=100))
        app.drive()
        app.story_motion.advance(10)
        self.assertEqual((608, 96), (app.x, app.y))
        app.drive()
        self.assertEqual('talk', app.display_request.kind)

    def test_manual_area_checks_count_tile_callbacks_not_render_frames(self):
        app = host(move())
        app.state.tables = dict(DATA.tables)
        app.state.tables['MainTask'] = dict(DATA.tables['MainTask'])
        app.state.tables['MainTask']['1'] = dict(DATA.tables['MainTask']['1'], counts='3')
        app.map.objects = [{'group': 'eventLayer', 'name': '10101',
                            'x': 64, 'y': 64, 'width': 128, 'height': 64}]
        app.process_player_areas()
        for _ in range(5):
            app.process_player_areas()
        self.assertEqual([1], app.state.task_counts['main:1'])
        app.x = 160
        app.process_player_areas()
        self.assertEqual([2], app.state.task_counts['main:1'])
        app.process_player_areas(force=True)
        self.assertEqual(4, app.state.main_state)
        self.assertEqual([], app.runtime.queue)

    def test_overlapping_areas_use_first_original_object(self):
        app = host(move())
        first = {'group': 'eventLayer', 'name': '10101', 'x': 64, 'y': 64, 'width': 64, 'height': 64}
        app.map.objects = [first, dict(first, name='10199')]
        app.process_player_areas()
        self.assertEqual({'10101'}, app.inside_areas)
        self.assertEqual(4, app.state.main_state)

    def test_save_restores_remaining_segment_and_callback(self):
        with tempfile.TemporaryDirectory() as folder:
            app = host(move())
            app.save_path = Path(folder)/'slot1.json'
            app.drive()
            app.story_motion.advance(.1)
            app.save()
            expected = copy.deepcopy(app.story_motion.actions)
            app.load_map = lambda mid, x, y: None
            app.story_motion.actions = []
            app.restore()
            self.assertEqual(expected, app.story_motion.actions)
            self.assertEqual('toplace', app.runtime.pending.kind)
            app.story_motion.advance(.31)
            app.drive()
            self.assertEqual((224, 96), (app.x, app.y))
            self.assertEqual('talk', app.display_request.kind)

    def test_real_original_npc_route_avoids_collision_layer(self):
        world = DATA.load_map('101')
        path = shortest_path(world, (1952, 1280), (1184, 1248),
                             lambda x, y: world.blocked((x+.5)*64, (y+.5)*64))
        self.assertIsNotNone(path)
        self.assertEqual([1184, 1248], path[-1])
        self.assertTrue(all(not world.blocked(*point) for point in path))

    def test_original_walking_frames_loop_and_mirror(self):
        from PIL import Image
        first = DATA.village_sprite('10001', 'walkdown', 0)
        later = DATA.village_sprite('10001', 'walkdown', 20)
        self.assertIsNotNone(first)
        self.assertIsNotNone(later)
        self.assertNotEqual(first.tobytes(), later.tobytes())
        self.assertEqual(first.tobytes(), DATA.village_sprite('10001', 'walkdown', 40).tobytes())
        left = DATA.village_sprite('10001', 'walkleft', 10)
        right = DATA.village_sprite('10001', 'walkright', 10)
        self.assertEqual(left.transpose(Image.Transpose.FLIP_LEFT_RIGHT).tobytes(), right.tobytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
