"""Runtime damage routing compared with the recovered ARM formula oracle."""
import copy
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from game_state import GameState
from battle import Battle, BattlePet, ATTRIBUTE_INDEX
from check_original_formulas import original

DATA = OriginalData(ROOT/'original-1.20.4')


class DamageChecks(unittest.TestCase):
    def setUp(self):
        state = GameState(DATA.tables, 45)
        a, b = copy.deepcopy(state.pets[:2])
        a.talents, b.talents = [], []
        self.battle = Battle(DATA.tables, [a], [b], random.Random(1))
        self.a, self.b = self.battle.player_active, self.battle.enemy_active

    def test_runtime_base_damage_uses_all_four_original_formula_branches(self):
        rng = random.Random(451)
        for _ in range(100):
            a, b = self.a, self.b
            a.stats, b.stats = [[rng.randint(1, 500) for _ in range(5)] for _ in range(2)]
            a.max_energy, b.max_energy = a.stats[1], b.stats[1]
            for kind, address, args in [
                ('power', 0x2b5a4c, [a.stats[2], b.stats[3], 0, 0]),
                ('speed', 0x2b5b2c, [a.stats[4], b.stats[4], b.stats[3], 0, 0]),
                ('defence', 0x2b5aa8, [a.stats[3], b.max_energy, b.stats[3], 0, 0]),
                ('energy', 0x2b5b98, [a.max_energy, b.max_energy, 0, 0])]:
                self.assertEqual(original(address, args), self.battle._base_damage(a, b, kind))

    def test_attribute_enum_is_power_speed_defence_energy(self):
        self.assertEqual({'0': 2, '1': 4, '2': 3, '3': 1}, ATTRIBUTE_INDEX)

    def test_restraint_and_critical_modify_base_before_skill_coefficient(self):
        battle, a, b = self.battle, self.a, self.b
        tables = copy.deepcopy(DATA.tables)
        tables['Pet'][a.pet.species]['restraint'] = '3'
        tables['Pet'][b.pet.species]['restraint'] = '4'
        tables['Contrast']['3']['mutual'] = '100,100,100,60,100,100'
        battle.tables = tables
        row = dict(tables['Skill']['300034'])
        expected = original(0x2b5c08, [int(100*110/100), 5, 120])
        b.hp = b.max_hp = 10000
        battle._deal(a, b, 100, 'power', crit=True, skill=row)
        self.assertEqual(expected, 10000-b.hp)
        self.assertEqual(expected, battle.events[-1]['amount'])

    def test_fixed_damage_has_no_unverified_random_jitter(self):
        amounts = []
        for _ in range(10):
            self.b.hp = self.b.max_hp = 10000
            self.battle._deal(self.a, self.b, 100, 'power', crit=False)
            amounts.append(10000-self.b.hp)
        self.assertEqual(1, len(set(amounts)))

    def test_basic_attack_does_not_invent_energy_recovery(self):
        self.a.energy = 1
        self.battle._attack(self.a, self.b)
        self.assertEqual(1, self.a.energy)
        self.assertEqual('attack', self.battle.events[0]['type'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
