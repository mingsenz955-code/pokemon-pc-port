"""Asset-independent bug regressions; these do not establish original-game parity."""
import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from game_state import GameState, Pet
from battle import Battle, BattlePet
from event_runtime import EventRuntime, PendingMechanic
from pc_game import NativeGame


def fixture():
    return {
        'Init': {'2': {'spriteId': '1', 'itemIds': '700001', 'itemCounts': '100',
                      'petIds': '0', 'budokanIds': '0', 'budokanLevels': '0',
                      'arenaIds': '0', 'arenaTitles': '0'}},
        'Pet': {'1': {'name': 'Test pet', 'attributeBase': '100,50,40,30,20', 'maxLevel': '170'}},
        'Money': {'700001': {'name': 'Gold'}},
        'Item': {'2': {'name': 'Potion', 'useType': '1', 'des': '恢复生命20'},
                 '3': {'name': 'Ether', 'useType': '1', 'des': '恢复能量20'},
                 '4': {'name': 'Full', 'useType': '1', 'des': '全回复'}},
        'PetItem': {'2': {'type': '1', 'parameters': '1,20'},
                    '3': {'type': '1', 'parameters': '2,20'},
                    '4': {'type': '2', 'parameters': '1,100,2,100'}},
        'MainTask': {'1': {'rewardIds': '2,999', 'rewardCounts': '1,1', 'nextTaskId': '2'}},
        'BranchTask': {}, 'Talent': {}, 'Contrast': {}, 'Cri': {},
        'Shop': {'1': {'goodsKid': '2', 'moneyType': '700001', 'price': '10'}},
        'Evolution': {}, 'VillageMap': {'7401': {}},
    }


class Regressions(unittest.TestCase):
    def setUp(self):
        self.tables = fixture()
        self.state = GameState(self.tables, 17)

    def pet(self):
        p = Pet('1', 1, [0]*5, [0]*5, [], [])
        p.heal(self.tables)
        self.state.pets.append(p)
        return p

    def test_reward_batch_rolls_back(self):
        before = self.state.payload()
        with self.assertRaises(KeyError):
            self.state.grant_many(['2', '999'], [1, 1])
        self.assertEqual(before, self.state.payload())

    def test_task_failure_is_retryable_without_duplication(self):
        before = self.state.payload()
        for _ in range(2):
            with self.assertRaises(KeyError):
                self.state.submit_task(1)
            self.assertEqual(before, self.state.payload())
        self.tables['MainTask']['1']['rewardIds'] = '2'
        self.tables['MainTask']['1']['rewardCounts'] = '1'
        self.assertTrue(self.state.submit_task(1))
        self.assertFalse(self.state.submit_task(1))
        self.assertEqual(1, self.state.count('2'))

    def test_late_task_error_rolls_back_rewards(self):
        self.tables['MainTask']['1'].update(rewardIds='2', rewardCounts='1', nextTaskId='bad')
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.state.submit_task(1)
        self.assertEqual(before, self.state.payload())

    def test_failed_pet_generation_restores_rng_and_object_identity(self):
        p = self.pet()
        team, inventory = self.state.pets, self.state.inventory
        before = self.state.payload()
        def fail(*args):
            self.state.rng.random()
            p.hp = 0
            self.state.pets.append(copy.deepcopy(p))
            raise ValueError('Generation interrupted')
        with patch.object(self.state, 'add_generated_pet', side_effect=fail):
            with self.assertRaises(ValueError):
                self.state.grant_many(['2', '1'], [1, 1])
        self.assertEqual(before, self.state.payload())
        self.assertIs(team, self.state.pets)
        self.assertIs(inventory, self.state.inventory)
        self.assertIs(p, self.state.pets[0])

    def test_reject_mismatched_cost_and_reward_arrays(self):
        for operation in (self.state.consume, self.state.grant_many):
            with self.assertRaises(ValueError):
                operation(['2', '3'], [1])

    def test_duplicate_cost_is_aggregated_before_deduction(self):
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.state.consume(['700001', '700001'], [60, 60])
        self.assertEqual(before, self.state.payload())

    def test_negative_late_reward_is_atomic(self):
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.state.grant_many(['2', '3'], [1, -1])
        self.assertEqual(before, self.state.payload())

    def test_invalid_shop_quantities_and_price(self):
        before = self.state.payload()
        for quantity in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                self.state.buy('Shop', '1', quantity)
        self.tables['Shop']['1']['price'] = '-10'
        with self.assertRaises(ValueError):
            self.state.buy('Shop', '1')
        self.assertEqual(before, self.state.payload())

    def test_buy_deducts_once(self):
        self.state.buy('Shop', '1', 2)
        self.assertEqual(80, self.state.count('700001'))
        self.assertEqual(2, self.state.count('2'))

    def test_energy_item_selects_energy_deficit(self):
        injured, tired = self.pet(), self.pet()
        injured.hp -= 10
        tired.energy -= 25
        self.state.grant('3', 1)
        self.state.use_item('3')
        self.assertEqual(45, tired.energy)
        self.assertEqual(90, injured.hp)
        self.assertEqual(0, self.state.count('3'))

    def test_full_recovery_works_with_only_energy_missing(self):
        p = self.pet()
        p.energy = 1
        self.state.grant('4', 1)
        self.state.use_item('4')
        self.assertEqual(50, p.energy)

    def test_no_effect_and_foreign_pet_do_not_consume(self):
        p = self.pet()
        self.state.grant('2', 2)
        for target in (p, copy.deepcopy(p)):
            with self.assertRaises(ValueError):
                self.state.use_item('2', target)
        self.assertEqual(2, self.state.count('2'))

    def test_bad_recovery_parameters_do_not_consume(self):
        p = self.pet()
        p.hp = 1
        self.tables['PetItem']['2']['parameters'] = '1'
        self.state.grant('2', 1)
        with self.assertRaises(ValueError):
            self.state.use_item('2', p)
        self.assertEqual(1, p.hp)
        self.assertEqual(1, self.state.count('2'))

    def test_evolution_failure_preserves_species_items_and_identity(self):
        p = self.pet()
        self.tables['Evolution']['1'] = {'level': '1', 'petId': '999', 'itemIds': '2', 'itemCounts': '1'}
        self.state.grant('2', 1)
        before = self.state.payload()
        with self.assertRaises(KeyError):
            self.state.evolve(p.uid)
        self.assertEqual(before, self.state.payload())
        self.assertIs(p, self.state.pets[0])

    def battle(self, result='win'):
        b = Battle.__new__(Battle)
        b.tables = self.tables
        b.drops, b.messages = [('2', 1)], []
        b.exp_gained = []
        b.caught_pet, b.result, b.rewards_applied = None, result, False
        return b

    def test_battle_rewards_cannot_repeat(self):
        b = self.battle()
        self.assertTrue(b.apply_rewards(self.state))
        self.assertFalse(b.apply_rewards(self.state))
        self.assertEqual(1, self.state.count('2'))
        self.assertEqual(1, len(b.messages))

    def test_battle_reward_failure_is_atomic(self):
        b = self.battle()
        b.drops.append(('999', 1))
        before = self.state.payload()
        with self.assertRaises(KeyError):
            b.apply_rewards(self.state)
        self.assertEqual(before, self.state.payload())
        self.assertFalse(b.rewards_applied)
        self.assertEqual([], b.messages)

    def test_incomplete_and_lost_battles_cannot_grant(self):
        for result in (None, 'lose', 'escape'):
            with self.assertRaises(ValueError):
                self.battle(result).apply_rewards(self.state)
        self.assertEqual(0, self.state.count('2'))

    def test_captured_pet_goes_to_bank_when_team_full_once(self):
        for _ in range(6):
            self.pet()
        b = self.battle('caught')
        b.caught_pet = copy.deepcopy(self.state.pets[0])
        b.apply_rewards(self.state)
        b.apply_rewards(self.state)
        self.assertEqual(6, len(self.state.pets))
        self.assertEqual([b.caught_pet], self.state.bank)
        self.assertEqual(['1'], self.state.encyclopedia)

    def test_hp_and_attack_talents_modify_only_their_stats(self):
        p = self.pet()
        self.tables['Talent'] = {'1': {'state': '24,9,20'}, '2': {'state': '25,9,30'}}
        p.talents = ['1', '2']
        unit = BattlePet(p, 'player', 0, self.tables)
        self.assertEqual(120, unit.max_hp)
        self.assertEqual([120, 50, 52, 30, 20], unit.stats)

    def test_missing_battle_result_stops_host(self):
        data = SimpleNamespace(event=lambda _: [])
        runtime = EventRuntime(data, self.state)
        runtime.file = 'test-event.json'
        runtime.sequence = [{'id': 1, 'type': 'fightover', 'parameters': {'win': 2, 'lose': 3}}]
        app = SimpleNamespace(display_request=None, runtime_error='', battle=None,
                              pending_wait=None, ui_open=False, wait_until=0,
                              runtime=runtime, state=self.state)
        NativeGame.drive(app)
        self.assertIn('缺少实际战斗结果', app.runtime_error)
        self.assertIsNone(runtime.battle_result)
        self.assertEqual(0, runtime.index)
        self.assertEqual('battleover', runtime.pending.kind)

    def test_load_during_battle_keeps_live_state(self):
        app = SimpleNamespace(battle=object(), event_issue='')
        NativeGame.restore(app)
        self.assertIn('战斗中', app.event_issue)

    def live_battle(self):
        p, reserve = self.pet(), self.pet()
        enemy = copy.deepcopy(p)
        enemy.uid = 'enemy'
        b = Battle(self.tables, [p, reserve], [enemy], self.state.rng,
                   can_catch=True, can_escape=True)
        return b

    def test_faint_requires_explicit_live_pet_selection(self):
        b = self.live_battle()
        b.player_active.hp = 0
        b._check_end()
        self.assertTrue(b.force_switch)
        self.assertEqual(0, b.player_index)
        self.assertEqual([], b.choose_skill(0))
        self.assertEqual([], b.choose_item('2'))
        self.assertEqual([], b.choose_escape())
        self.assertEqual(0, b.round)
        b.choose_switch(1)
        self.assertFalse(b.force_switch)
        self.assertEqual(1, b.player_index)
        self.assertEqual(0, b.round)

    def test_enemy_attack_targets_incoming_pet_after_switch(self):
        b = self.live_battle()
        first, incoming = b.player
        def execute(unit, target, action, side):
            if action['type'] == 'switch':
                b.player_index = action['index']
            elif side == 'enemy':
                target.take_damage(7)
        with patch.object(b, '_execute', side_effect=execute):
            b.choose_switch(1)
        self.assertEqual(100, first.hp)
        self.assertEqual(93, incoming.hp)

    def test_item_skipped_by_sleep_is_not_deducted(self):
        from battle import Buff
        from battle_ui import BattleUI
        b = self.live_battle()
        b.player_active.buffs.append(Buff('5', 3, '0', 2))
        self.state.grant('2', 1)
        ui = BattleUI.__new__(BattleUI)
        ui.battle, ui.app = b, SimpleNamespace(state=self.state)
        ui.selected, ui.screen, ui.notice = {'id': '2'}, 'confirm', ''
        ui._action('confirm_yes')
        self.assertEqual(1, self.state.count('2'))
        self.assertFalse(any(e['type'] == 'item_used' and e['side'] == 'player'
                             for e in b.events))

    def test_item_used_in_battle_deducts_once(self):
        from battle_ui import BattleUI
        b = self.live_battle()
        b.player_active.hp = 10
        self.state.grant('2', 2)
        ui = BattleUI.__new__(BattleUI)
        ui.battle, ui.app = b, SimpleNamespace(state=self.state)
        ui.selected, ui.screen, ui.notice = {'id': '2'}, 'confirm', ''
        ui._action('confirm_yes')
        self.assertEqual(1, self.state.count('2'))
        self.assertTrue(any(e['type'] == 'item_used' and e['side'] == 'player'
                            for e in b.events))

    def test_enemy_heals_itself_with_finite_inventory(self):
        b = self.live_battle()
        b.enemy_items = {'2': 1}
        b.enemy_active.hp = 10
        player_hp = b.player_active.hp
        action = {'type': 'item', 'id': '2'}
        b._execute(b.enemy_active, b.player_active, action, 'enemy')
        self.assertEqual(30, b.enemy_active.hp)
        self.assertEqual(player_hp, b.player_active.hp)
        self.assertIsNone(b._enemy_heal_item())
        b._execute(b.enemy_active, b.player_active, action, 'enemy')
        self.assertEqual(30, b.enemy_active.hp)


if __name__ == '__main__':
    unittest.main(verbosity=2)
