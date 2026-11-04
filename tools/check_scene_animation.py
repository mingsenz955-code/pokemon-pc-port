"""No-window regressions for player direction, authored idle clips and map NPC patrols."""
import copy
import json
from pathlib import Path
import sys
from types import MethodType, SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from check_story_motion import host, move, DATA
from ccs_timeline import sample_frame
from npc_motion import NpcMotion
from pc_game import NativeGame


def world_host():
    app = host(move())
    app.map = DATA.load_map(101)
    app.actors = MethodType(NativeGame.actors, app)
    app.runtime.file, app.runtime.sequence, app.runtime.pending = '', [], None
    app.npc_motion = NpcMotion(app, seed=7)
    app.npc_motion.reset()
    return app


class AnimationChecks(unittest.TestCase):
    def test_completed_plot_facing_does_not_lock_keyboard_direction(self):
        app = host(move())
        app.player_sprite, app.player_walking, app.scene_animation_time = '10001', False, 1
        app.story_motion.faces['101:1:0'] = 'standright'
        app.data = SimpleNamespace(village_sprite=lambda sid, animation, frame: (animation, frame))
        for direction in ('up', 'down', 'left', 'right'):
            self.assertEqual('stand'+direction, app.player_image('stand'+direction)[0])
        app.player_walking = True
        self.assertEqual('walkleft', app.player_image('standleft')[0])

    def test_manual_displacement_and_guide_displacement_turn_player(self):
        app = host(move())
        app.noclip = False
        for target, face in [((80, 96), 'standleft'), ((96, 96), 'standright'),
                             ((96, 80), 'standup'), ((96, 96), 'standdown')]:
            app.player_walking = False
            app.move_to(*target)
            self.assertEqual(face, app.face)
            self.assertTrue(app.player_walking)

    def test_idle_timeline_changes_and_linear_tracks_interpolate(self):
        _, source = DATA.armature_source('npc1')
        clip = next(m for m in source['animation_data'][0]['mov_data'] if m['name'] == 'standdown')
        track = next(b['frame_data'] for b in clip['mov_bone_data'] if b['name'] == 'z_fa1')
        self.assertAlmostEqual((track[0]['kX']+track[1]['kX'])/2, sample_frame(track, 7.5)['kX'])
        first, middle = (DATA.village_sprite('10001', 'standdown', t) for t in (0, 7))
        self.assertNotEqual(first.tobytes(), middle.tobytes())
        self.assertIn('origin', middle.info)
        left = DATA.village_sprite('10001', 'walkleft', 7)
        right = DATA.village_sprite('10001', 'walkright', 7)
        self.assertAlmostEqual(left.width-left.info['origin'][0], right.info['origin'][0])

    def test_only_configured_visible_npcs_patrol(self):
        app = world_host()
        self.assertEqual({'10103', '10111', '10112', '10115'}, set(app.npc_motion.controllers))
        gameplay_rng = app.state.rng.getstate()
        for _ in range(100):
            app.npc_motion.advance(.2)
        moved = {key.split(':')[-1] for key in app.state.positions}
        self.assertTrue(moved)
        self.assertTrue(moved <= {'10103', '10111', '10112'})
        self.assertNotIn('10115', moved)
        self.assertEqual(gameplay_rng, app.state.rng.getstate())

    def test_ambient_completion_cannot_resume_plot_instruction(self):
        app = world_host()
        for controller in app.npc_motion.controllers.values():
            controller['wait'] = 1
        app.npc_motion.advance(1)
        app.runtime.start('motion-check.json')
        request = app.runtime.next()
        app.npc_motion.advance(10)
        self.assertIs(request, app.runtime.pending)
        self.assertEqual(0, app.runtime.index)
        self.assertEqual([], app.npc_motion.motion.actions)

    def test_patrol_snapshot_preserves_rng_routes_and_remaining_wait(self):
        app = world_host()
        for _ in range(30):
            app.npc_motion.advance(.2)
        snapshot = json.loads(json.dumps(app.npc_motion.snapshot()))
        other = world_host()
        other.state.positions = copy.deepcopy(app.state.positions)
        other.story_motion.faces = copy.deepcopy(app.story_motion.faces)
        other.npc_motion.restore(snapshot)
        for _ in range(50):
            app.npc_motion.advance(.2)
            other.npc_motion.advance(.2)
        self.assertEqual(app.state.positions, other.state.positions)
        self.assertEqual(app.npc_motion.snapshot(), other.npc_motion.snapshot())


if __name__ == '__main__':
    unittest.main(verbosity=2)
