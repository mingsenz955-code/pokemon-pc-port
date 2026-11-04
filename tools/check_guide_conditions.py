"""Data-only regression checks for original task types and encounter references.

Does not launch windows, run the player's save, or assert full game completion.
"""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from game_state import GameState
from guide import GuideResolver

DATA = OriginalData(ROOT/'original-1.20.4')


class GuideConditions(unittest.TestCase):
    def setUp(self):
        self.state = GameState(DATA.tables, seed=4)
        self.resolver = GuideResolver(DATA, self.state)

    def main_target(self, key, status=3):
        return self.resolver.from_task('main', str(key), DATA.tables['MainTask'][str(key)], status)

    def test_battle_task_targets_actor_not_battle_type_as_map(self):
        for task, expected_map in [(11, 5901), (37, 6501)]:
            target = self.main_target(task)
            self.assertEqual(('npc', expected_map), (target.kind, target.map_id))

    def test_script_initially_hidden_actor_still_has_location(self):
        target = self.main_target(16)
        self.assertEqual(('npc', 115), (target.kind, target.map_id))
        self.assertEqual((1760, 768), (target.x, target.y))

    def test_type_seven_is_map_arrival(self):
        target = self.main_target(14)
        self.assertEqual(('map', 115), (target.kind, target.map_id))

    def test_obstacle_does_not_invent_level_or_map(self):
        row = DATA.tables['BranchTask']['6601']
        target = self.resolver.from_task('branch', '6601', row, 3)
        self.assertEqual('obstacle', target.kind)
        self.assertEqual(0, target.map_id)

    def test_completed_fight_targets_submit_actor(self):
        target = self.main_target(37, 4)
        self.assertEqual(('npc', 6501), (target.kind, target.map_id))
        self.assertIn('650101', target.detail)

    def test_specific_pet_resolves_village_enemy_indirection(self):
        mid, row = next((key, row) for key, row in DATA.tables['VillageMap'].items()
                        if row.get('enemyIds', '0') != '0')
        enemy_id = row['enemyIds'].split(',')[0]
        pet_id = int(DATA.tables['VillageEnemy'][enemy_id]['petId'])
        point = self.resolver.catch_point(pet_id, -1, int(mid))
        self.assertIsNotNone(point)
        self.assertEqual(int(mid), point[0])
        self.assertIsNone(self.resolver.catch_point(999999999, -1, int(mid)))

    def test_pet_kind_and_id_must_match_same_encounter(self):
        tables = {'VillageMap': {'101': {'enemyIds': '901,902'}},
                  'VillageEnemy': {'901': {'petId': '1'}, '902': {'petId': '2'}},
                  'Pet': {'1': {'keyId': '1', 'kind': '5'}, '2': {'keyId': '2', 'kind': '6'}}}
        resolver = GuideResolver(SimpleNamespace(tables=tables), self.state)
        self.assertIsNone(resolver.catch_point(1, 6, 101))

    def test_task_fields_are_pet_id_then_kind_then_map(self):
        mid, row = next((key, row) for key, row in DATA.tables['VillageMap'].items()
                        if row.get('enemyIds', '0') != '0')
        pet_id = DATA.tables['VillageEnemy'][row['enemyIds'].split(',')[0]]['petId']
        kind = DATA.tables['Pet'][pet_id]['kind']
        task = dict(DATA.tables['MainTask']['6'], conditions=f'{pet_id},{kind},{mid}')
        target = self.resolver.from_task('main', '6', task, 3)
        self.assertIsNotNone(target)
        self.assertEqual(('catch', int(mid)), (target.kind, target.map_id))


if __name__ == '__main__':
    unittest.main(verbosity=2)
