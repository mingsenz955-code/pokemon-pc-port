"""Real-table traversal matrix and native movement/save integration checks."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from game_state import GameState
from mounts import Mounts
from original_data import OriginalData, OriginalMap
from pc_game import NativeGame

TABLES = json.loads((ROOT/'original-1.20.4/tables.json').read_text('utf-8'))


class MountChecks(unittest.TestCase):
    def setUp(self):
        self.state = GameState(TABLES, seed=8)
        self.state.rides = []
        self.state.encyclopedia = []
        self.mounts = Mounts(self.state)

    def test_original_mount_terrain_and_map_matrix(self):
        expected = {500001: {0}, 500002: {2}, 500003: {0, 1, 2, 3},
                    500004: {0, 3}, 500005: {0}}
        for key, allowed in expected.items():
            self.state.rides, self.state.ride = [key], key
            for map_type in (1, 2, 3, 4):
                disabled = map_type == 1 or key == 500003 and map_type == 3
                for terrain in (0, 1, 2, 3, 4, None):
                    with self.subTest(mount=key, map=map_type, terrain=terrain):
                        self.assertEqual(self.mounts.can_enter(terrain, map_type),
                                         terrain == 0 or terrain in allowed and not disabled)

    def test_walking_blocks_every_nonzero_category(self):
        self.assertTrue(self.mounts.can_enter(0, 2))
        for terrain in (1, 2, 3, 4, None):
            self.assertFalse(self.mounts.can_enter(terrain, 2))

    def test_auto_board_water_and_special_mount_and_dismount_on_land(self):
        self.state.rides = [500002, 500004]
        self.assertTrue(self.mounts.can_enter(2, 2))
        self.assertEqual(self.state.ride, 0)  # Collision probes cannot mount.
        self.mounts.enter(2, 2)
        self.assertEqual(self.state.ride, 500002)
        self.mounts.enter(3, 2)
        self.assertEqual(self.state.ride, 500004)
        self.mounts.enter(0, 2)
        self.assertEqual(self.state.ride, 500004)
        self.mounts.select(500002, 2, 2)
        self.mounts.enter(0, 2)
        self.assertEqual(self.state.ride, 0)

    def test_flying_requires_manual_selection_and_respects_map_ban(self):
        self.state.rides = [500003]
        self.assertFalse(self.mounts.can_enter(1, 2))
        self.mounts.select(500003, 0, 2)
        self.assertTrue(self.mounts.can_enter(1, 2))
        self.assertFalse(self.mounts.can_enter(1, 3))
        self.mounts.enter(0, 3)
        self.assertEqual(self.state.ride, 0)

    def test_ownership_selection_and_illegal_dismount(self):
        self.state.ride = 500003
        self.assertFalse(self.mounts.can_enter(1, 2))
        with self.assertRaises(ValueError):
            self.mounts.select(500003, 0, 2)
        self.state.rides = [500002]
        self.mounts.select(500002, 2, 2)
        with self.assertRaises(ValueError):
            self.mounts.select(0, 2, 2)
        with self.assertRaises(ValueError):
            self.mounts.select(500002, 0, 2)
        self.assertEqual(self.state.ride, 500002)

    def test_trial_uses_its_terrain_without_granting_ownership(self):
        self.state.trial_ride = 500003
        self.assertTrue(self.mounts.can_enter(1, 2))
        self.assertFalse(self.mounts.can_enter(1, 3))
        self.mounts.enter(0, 2)
        self.assertEqual(self.state.trial_ride, 500003)
        self.assertEqual(self.state.rides, [])
        self.state.trial_ride = 0
        self.assertFalse(self.mounts.can_enter(1, 2))

    def test_acquired_mount_and_active_ride_survive_save(self):
        self.state.record_pet('100038')
        self.state.record_pet('100038')
        self.assertEqual(self.state.rides, [500002])
        self.mounts.enter(2, 2)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'slot.json'
            self.state.save(path)
            restored = GameState.load(TABLES, path)
        self.assertEqual(restored.rides, [500002])
        self.assertEqual(restored.ride, 500002)
        self.assertTrue(Mounts(restored).can_enter(2, 2))

    def test_legacy_save_recovers_mount_from_acquired_pet(self):
        self.state.encyclopedia = ['100038']
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'slot.json'
            self.state.save(path)
            restored = GameState.load(TABLES, path)
        self.assertIn(500002, restored.rides)

    @staticmethod
    def fixture_map():
        result = OriginalMap.__new__(OriginalMap)
        result.width, result.height, result.tw, result.th = 4, 1, 64, 64
        result.info = {'mapType': '2'}
        result.layers = [('collideLayer', [0, 1, 2, 3], 1)]
        result.tile_properties = lambda gid: {'collideTile': str(gid)}
        return result

    def test_native_movement_uses_mount_policy_and_preserves_blocked_position(self):
        host = NativeGame.__new__(NativeGame)
        host.state, host.map, host.noclip = self.state, self.fixture_map(), False
        host.x, host.y = 32, 32
        host.move_to(160, 32)
        self.assertEqual((host.x, host.y), (32, 32))
        self.state.rides = [500002]
        host.move_to(160, 32)
        self.assertEqual((host.x, host.y, self.state.ride), (160, 32, 500002))
        host.move_to(96, 32)  # Wall cannot be crossed by a water mount.
        self.assertEqual(host.x, 160)
        host.move_to(-1, 32)
        self.assertEqual(host.x, 160)
        host.move_to(32, 32)
        self.assertEqual(self.state.ride, 0)

    def test_real_maps_preserve_all_collision_categories(self):
        data = OriginalData(ROOT/'original-1.20.4')
        found = set()
        for key in TABLES['VillageMap']:
            world = data.load_map(key)
            for name, values, _ in world.layers:
                if name != 'collideLayer':
                    continue
                for gid in set(values):
                    index = values.index(gid)
                    x, y = index % world.width*world.tw+1, index//world.width*world.th+1
                    category = int(world.tile_properties(gid).get('collideTile', 0))
                    self.assertEqual(world.terrain_at(x, y), category)
                    self.assertEqual(world.blocked(x, y), category != 0)
                    found.add(category)
        self.assertTrue({0, 1, 2, 3}.issubset(found))


if __name__ == '__main__':
    unittest.main(verbosity=2)
