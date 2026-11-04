"""Real 1.20.4 economic state checks, not a full-game equivalence claim."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from activities import Activities
from game_state import GameState
from item_effects import recovery

TABLES = json.loads((ROOT/'original-1.20.4/tables.json').read_text(encoding='utf-8'))


class EconomicChecks(unittest.TestCase):
    def setUp(self):
        self.state = GameState(TABLES, 509)
        self.state.initialize(1)
        self.state.grant('700002', 100)
        self.activity = Activities(self.state)

    def test_all_draw_modes_use_their_original_pools_and_prices(self):
        for kind, price, count in ((1, 10, 1), (2, 25, 1), (3, 50, 3)):
            before = self.state.count('700002')
            pets = self.activity.draw_pets(kind)
            self.assertEqual(count, len(pets))
            self.assertEqual(price, before-self.state.count('700002'))
            row = TABLES['LuckyDraw'][str(kind)]
            for index, pet in enumerate(pets):
                pool = row['rarePetIds' if kind == 3 and index == 0 else 'petIds'].split(',')
                self.assertIn(pet.species, pool)
                self.assertEqual(1, pet.level)
                self.assertGreaterEqual(pet.quality, 1)
                for value, intervals in zip(pet.growth, json.loads(row['attUpVarInterval'])):
                    self.assertTrue(any(low <= value <= high for low, high in intervals))

    def test_free_draw_cooldown_and_payment_are_persisted(self):
        balance = self.state.count('700002')
        self.activity.draw_pets(1, free=True, now=10000)
        self.assertEqual(balance, self.state.count('700002'))
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.activity.draw_pets(1, free=True, now=10001)
        self.assertEqual(before, self.state.payload())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'save.json'
            self.state.save(path)
            restored = GameState.load(TABLES, path)
            self.assertEqual(17200, restored.activities['lucky_free_at'])
            with self.assertRaises(ValueError):
                Activities(restored).draw_pets(1, free=True, now=17199)
            Activities(restored).draw_pets(1, free=True, now=17200)

    def test_full_bank_rejects_draw_before_charge_or_rng_use(self):
        while len(self.state.pets) < 6:
            self.state.pets.append(self.state.preset_pet(1))
        self.state.inventory['700005'] = 0
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.activity.draw_pets(3)
        self.assertEqual(before, self.state.payload())

    def test_insufficient_badges_do_not_roll_pet_or_change_inventory(self):
        self.state.inventory['700002'] = 0
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.activity.draw_pets(2)
        self.assertEqual(before, self.state.payload())

    def test_roulette_has_original_twelve_slots_and_group_counts(self):
        from collections import Counter
        board = self.activity.roulette_board(now=1700000000)
        self.assertEqual(12, len(board))
        self.assertEqual({k: int(r['boxCount']) for k, r in TABLES['LuckyRoulette'].items()},
                         dict(Counter(r['group'] for r in board)))
        for reward in board:
            row = TABLES['LuckyRoulette'][reward['group']]
            self.assertIn(reward['item'], row['itemIds'].split(','))
            self.assertEqual(int(row['hitPro']), reward['weight'])
        rng = self.state.rng.getstate()
        self.assertEqual(board, self.activity.roulette_board(now=1700000001))
        self.assertEqual(rng, self.state.rng.getstate())

    def test_roulette_ticket_and_refresh_badge_are_consumed_once(self):
        self.state.grant('220009', 1)
        self.activity.roulette_board(now=1700000000)
        board = copy.deepcopy(self.state.activities['roulette_board'])
        self.activity.spin_roulette(now=1700000000)
        self.assertEqual(0, self.state.count('220009'))
        self.assertEqual(board, self.state.activities['roulette_board'])
        self.activity.roulette_board(now=1700000001, paid_refresh=True)
        self.assertEqual(99, self.state.count('700002'))

    def test_roulette_failure_restores_ticket_reward_and_rng(self):
        self.state.grant('220009', 1)
        self.state.activities['roulette_board'] = [{'item': 'does-not-exist', 'count': 1, 'weight': 100}]
        self.state.activities['roulette_refreshed_at'] = 1700000000
        before = self.state.payload()
        with self.assertRaises(KeyError):
            self.activity.spin_roulette(now=1700000001)
        self.assertEqual(before, self.state.payload())

    def test_bank_obeys_six_carried_slots(self):
        for _ in range(7):
            self.state.add_preset(2)
        self.assertEqual((6, 1), (len(self.state.pets), len(self.state.bank)))
        pet = self.state.pets[0]
        self.state.move_pet(pet.uid, to_bank=True)
        self.assertEqual((5, 2), (len(self.state.pets), len(self.state.bank)))
        self.state.move_pet(pet.uid, to_bank=False)
        self.assertIs(pet, self.state.pets[-1])

    def test_pet_shop_uses_fixed_original_level_and_attributes(self):
        self.state.grant('700001', 1000)
        pet = self.state.buy_pet('601')
        self.assertEqual('100008', pet.species)
        self.assertEqual(5, pet.level)
        self.assertEqual([1]*5, pet.variation)
        self.assertEqual(600, self.state.count('700001'))

    def test_single_medal_exchange_cannot_repeat_after_save(self):
        key = next(k for k,r in TABLES['MedalShop'].items() if r['repeat']=='0')
        row = TABLES['MedalShop'][key]
        self.state.grant(row['moneyType'], int(row['price'])*2)
        self.state.buy('MedalShop', key)
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.state.buy('MedalShop', key)
        self.assertEqual(before, self.state.payload())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'save.json'
            self.state.save(path)
            restored = GameState.load(TABLES, path)
            with self.assertRaises(ValueError):
                restored.buy('MedalShop', key)

    def test_original_percentage_and_revival_items(self):
        result = recovery(TABLES['PetItem']['230006'], 10, 20, 201, 101)
        self.assertEqual((110, 70), (result.hp, result.energy))
        result = recovery(TABLES['PetItem']['230008'], 0, 0, 201, 101)
        self.assertEqual((60, 30), (result.hp, result.energy))
        with self.assertRaisesRegex(ValueError, '复活石'):
            recovery(TABLES['PetItem']['230001'], 0, 0, 201, 101)

    def test_training_caps_and_failure_without_consumption(self):
        pet = self.state.add_preset(1)
        self.state.grant('230014', 3)
        pet.training = [500, 500, 995, 0, 0]
        self.state.use_item('230014', pet)
        self.assertEqual([500, 500, 1000, 0, 0], pet.training)
        self.assertEqual(2, self.state.count('230014'))
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.state.use_item('230014', pet)
        self.assertEqual(before, self.state.payload())

    def test_nurse_always_free_with_or_without_cards(self):
        state=self.state
        for times in (0,1,8):
            state.inventory['700006']=times
            before=dict(state.inventory)
            self.assertEqual((None,0),state.cure_party())
            self.assertEqual(state.inventory,before)

    def test_skill_tutor_cost_replacement_and_scroll(self):
        pet = self.state.add_preset(1)
        skills = TABLES['Pet'][pet.species]['skillIds'].split(',')
        target = next(k for k in skills if k not in pet.skills)
        row = TABLES['Skill'][target]
        self.state.inventory[row['moneyId']] = int(row['moneyCount'])
        pet.skills = skills[:4]
        target = next(k for k in skills if k not in pet.skills)
        row = TABLES['Skill'][target]
        self.state.inventory[row['moneyId']] = int(row['moneyCount'])
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.state.learn_skill(pet.uid, target)
        self.assertEqual(before, self.state.payload())
        self.state.learn_skill(pet.uid, target, replace=1)
        self.assertEqual(target, pet.skills[1])
        self.assertEqual(0, self.state.count(row['moneyId']))
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.state.learn_skill(pet.uid, target, replace=0)
        self.assertEqual(before, self.state.payload())
        item, data = next((k, v) for k, v in TABLES['SkillItem'].items()
                          if v['skillId'] in TABLES['Skill'] and v['skillId'] not in pet.skills)
        self.state.grant(item, 1)
        self.state.learn_skill(pet.uid, data['skillId'], scroll=item, replace=2)
        self.assertEqual(data['skillId'], pet.skills[2])
        self.assertEqual(0, self.state.count(item))

    def test_passive_scrolls_have_two_slots_separate_from_natural_talents(self):
        pet = self.state.add_preset(1)
        pet.talents = ['400101']
        scrolls = [(k, v['skillId']) for k, v in TABLES['SkillItem'].items()
                   if v['skillId'] in TABLES['Talent']][:3]
        for item, key in scrolls:
            self.state.grant(item, 1)
        for item, key in scrolls[:2]:
            self.state.learn_skill(pet.uid, key, scroll=item)
        before = self.state.payload()
        item, key = scrolls[2]
        with self.assertRaises(ValueError):
            self.state.learn_skill(pet.uid, key, scroll=item)
        self.assertEqual(before, self.state.payload())
        self.state.learn_skill(pet.uid, key, scroll=item, replace=0)
        self.assertEqual(['400101', key, scrolls[1][1]], pet.talents)
        self.assertEqual(0, self.state.count(item))

    def test_breakthrough_cost_heal_and_atomic_failure(self):
        pet = self.state.add_preset(1)
        row = TABLES['PetTuPo']['1']
        self.state.inventory[row['costMoneyType']] = int(row['costMoneyCount'])
        self.state.inventory[row['stuffId']] = int(row['stuffCount'])-1
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.state.breakthrough_pet(pet.uid)
        self.assertEqual(before, self.state.payload())
        self.state.grant(row['stuffId'], 1)
        pet.hp = pet.energy = 0
        self.state.breakthrough_pet(pet.uid)
        self.assertEqual(1, pet.breakthrough)
        self.assertEqual(0, self.state.count(row['costMoneyType']))
        self.assertEqual(0, self.state.count(row['stuffId']))
        self.assertEqual(tuple(pet.stats(TABLES)[:2]), (pet.hp, pet.energy))

    def cards(self, player_star=5, enemy_star=1):
        self.state.grant('220008', 1)
        match = self.activity.start_cards()
        for card in match['player']:
            card['star'] = player_star
        for card in match['enemy']:
            card['star'] = enemy_star
        return match

    def test_card_deal_cost_resume_and_invalid_play(self):
        self.state.grant('220008', 2)
        match = self.activity.start_cards()
        self.assertEqual(1, self.state.count('220008'))
        for hand in ('player', 'enemy'):
            self.assertEqual(5, len(match[hand]))
            for card in match[hand]:
                self.assertEqual(int(TABLES['Pet'][card['species']]['starLevel']), card['star'])
        before = self.state.payload()
        for callback in (self.activity.start_cards, lambda: self.activity.play_card(-1),
                         lambda: self.activity.play_card(True)):
            with self.assertRaises(ValueError):
                callback()
            self.assertEqual(before, self.state.payload())
        self.activity.play_card(0)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'cards.json'
            self.state.save(path)
            restored = GameState.load(TABLES, path)
            self.assertEqual(self.state.activities['cards'], restored.activities['cards'])
            with self.assertRaises(ValueError):
                Activities(restored).play_card(0)

    def test_cards_three_wins_end_early_and_only_one_reward(self):
        match = self.cards()
        for index in range(3):
            self.activity.play_card(index)
        self.assertEqual((1, [3, 0], 3), (match['result'], match['score'], match['round']))
        self.assertEqual(3, len(set(match['enemy_used'])))
        row = TABLES['CardLegend']['1']
        self.assertIn((match['reward']['item'], match['reward']['count']),
                      list(zip(row['itemIds'].split(','), map(int, row['itemCounts'].split(',')))))
        self.activity.claim_cards()
        before = self.state.payload()
        self.assertIsNone(self.activity.claim_cards())
        self.assertEqual(before, self.state.payload())

    def test_card_ties_and_loss_do_not_grant_rewards(self):
        for ours, theirs, result, rounds in ((2, 2, 0, 5), (1, 5, -1, 3)):
            match = self.cards(ours, theirs)
            for index in range(rounds):
                self.activity.play_card(index)
            self.assertEqual(result, match['result'])
            self.assertIsNone(match['reward'])
            with self.assertRaises(ValueError):
                self.activity.claim_cards()

    def test_card_insufficient_ticket_keeps_rng(self):
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.activity.start_cards()
        self.assertEqual(before, self.state.payload())

    def test_fixed_egg_material_hatching_and_reward_collection(self):
        self.state.grant('250006', 1)
        self.activity.put_egg(0, '250006')
        self.assertEqual(0, self.state.count('250006'))
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.activity.hatch(0)
        self.assertEqual(before, self.state.payload())
        self.activity.add_hatch_exp(1000)
        egg = self.state.activities['eggs']['0']
        self.assertEqual(200, egg['exp'])
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.activity.hatch(0)
        self.assertEqual(before, self.state.payload())
        self.state.grant('240002', 1)
        pet = self.activity.hatch(0)
        self.assertEqual('100007', pet.species)
        self.assertEqual([2., 2., 1., 1., 1.], pet.variation)
        self.assertEqual([4.5, 5., 4.5, 5.5, 4.5], pet.growth)
        self.assertEqual(0, self.state.count('240002'))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'egg.json'
            self.state.save(path)
            restored = GameState.load(TABLES, path)
            received = Activities(restored).take_egg(0)
            self.assertEqual(pet.uid, received.uid)
            self.assertIn(received, restored.pets)
            with self.assertRaises(ValueError):
                Activities(restored).take_egg(0)

    def test_money_hatch_bypasses_materials_and_exp_and_preserves_full_bank_reward(self):
        self.state.grant('250001', 1)
        self.activity.put_egg(9, '250001')
        self.state.inventory['700001'] = 500
        pet = self.activity.hatch(9, use_money=True)
        self.assertIn(pet.species, TABLES['HatchItem']['250001']['petIds'].split(','))
        self.assertEqual(0, self.state.count('700001'))
        while len(self.state.pets) < 6:
            self.state.pets.append(self.state.preset_pet(1))
        self.state.inventory['700005'] = 0
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.activity.take_egg(9)
        self.assertEqual(before, self.state.payload())
        self.state.inventory['700005'] = 1
        received = self.activity.take_egg(9)
        self.assertEqual(pet.uid, received.uid)
        self.assertIn(received, self.state.bank)

    def test_egg_takeback_refunds_one_egg_and_resets_progress(self):
        self.state.grant('250001', 1)
        self.activity.put_egg(0, '250001')
        self.activity.add_hatch_exp(100)
        self.activity.take_egg(0)
        self.assertEqual(1, self.state.count('250001'))
        self.activity.put_egg(0, '250001')
        self.assertEqual(0, self.state.activities['eggs']['0']['exp'])
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.activity.put_egg(0, '250001')
        self.assertEqual(before, self.state.payload())

    def test_village_chest_rewards_only_once_after_reload(self):
        self.activity.open_village_chest('60301')
        self.assertEqual(1, self.state.count('260003'))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'chest.json'
            self.state.save(path)
            restored = GameState.load(TABLES, path)
            before = restored.payload()
            with self.assertRaises(ValueError):
                Activities(restored).open_village_chest('60301')
            self.assertEqual(before, restored.payload())


if __name__ == '__main__':
    unittest.main(verbosity=2)
