"""Check original asset timeline coverage and native battle animation playback."""
from pathlib import Path
import sys
import unittest
import json

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from spine_animation import channels, curve_percent, duration, sample_pose
from spine_renderer import load_skeleton, animated_frame


class SpineChecks(unittest.TestCase):
    def test_bezier_stepped_rotation_and_pre_first_frame(self):
        self.assertEqual(curve_percent('stepped', .9), 0)
        self.assertAlmostEqual(curve_percent([0, 0, 1, 1], .5), .5, places=5)
        self.assertIsNone(channels([{'time': 1, 'x': 5}], 0, ['x'], [0]))
        values = channels([{'angle': 170}, {'time': 1, 'angle': -170}], .5,
                          ['angle'], [0], angle=True)
        self.assertAlmostEqual(values[0], 180)

    def test_all_original_pet_poses_sample_without_changing_setup(self):
        tables = json.loads((ROOT/'original-1.20.4/tables.json').read_text('utf-8'))
        paths = {ROOT/'original-1.20.4/assets/Sprite/Spine'/(p['filePath']+'.json')
                 for p in tables['Pet'].values()}
        sampled, constraints = 0, []
        for path in sorted(paths):
            if not path.exists():
                continue
            setup = load_skeleton(str(path))
            before = json.dumps(setup, sort_keys=True)
            for name, animation in setup.get('animations', {}).items():
                length = duration(animation)
                for seconds in (0, length*.4, length):
                    pose = sample_pose(setup, name, seconds, loop=False)
                    self.assertEqual(len(pose['bones']), len(setup['bones']))
                    self.assertEqual({s['name'] for s in pose['slots']},
                                     {s['name'] for s in setup['slots']})
                    sampled += 1
                if animation.get('ik'):
                    constraints.append([path.name, name])
            self.assertEqual(before, json.dumps(setup, sort_keys=True))
        folder = ROOT/'outputs/verification'
        folder.mkdir(parents=True, exist_ok=True)
        (folder/'spine-animation-coverage.json').write_text(json.dumps({
            'sampled_poses': sampled, 'unique_pet_skeletons': len(paths),
            'ik_timelines_pending': constraints,
            'original_binary_or_frame_parity': 'not established by this coverage check'
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        self.assertGreater(sampled, 1000)

    def test_original_stand_attack_hit_dead_produce_distinct_rendered_frames(self):
        path = str(ROOT/'original-1.20.4/assets/Sprite/Spine/penhuolongchaojinhua.json')
        images = []
        folder = ROOT/'outputs/verification/spine-animation'
        folder.mkdir(parents=True, exist_ok=True)
        for name in ('stand', 'attack', 'underattack', 'dead'):
            image, offset, height = animated_frame(path, name, .2, loop=False)
            self.assertIsNotNone(image.getbbox())
            self.assertGreater(height, 0)
            images.append((image.size, image.tobytes(), offset))
            image.save(folder/(name+'.png'))
        self.assertEqual(len({hash(entry) for entry in images}), 4)


if __name__ == '__main__':
    unittest.main(verbosity=2)
