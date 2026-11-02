"""Global reward labels, all bag categories, trial NPCs and native result input."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PIL import ImageChops
import check_single_window_flows as fixtures
from achievements import Achievements
from activities import Activities
from battle import make_wild_battle
from battle_ui import BattleUI
from game_state import GameState


class GlobalChecks(unittest.TestCase):
    setUp = fixtures.SingleWindowChecks.setUp
    tearDown = fixtures.SingleWindowChecks.tearDown
    open = fixtures.SingleWindowChecks.open
    click = fixtures.SingleWindowChecks.click
    save_panel = fixtures.SingleWindowChecks.save_panel

    def test_all_reward_names_fit_their_original_label_background(self):
        a = self.app
        names = [r['name'] for table in ['Item', 'Pet', 'Money'] for r in a.data.tables[table].values()]
        for name in names:
            a.cocos_ui.render('GetItemUIItemUI', (128, 167), text={'item_name_Text': name})
            label = a.cocos_ui.rects['item_name_Text']
            box = a.cocos_ui.rects['nameBg_Image']
            self.assertGreaterEqual(label[0], box[0]+2, name)
            self.assertGreaterEqual(label[1], box[1]+2, name)
            self.assertLessEqual(label[2], box[2]-2, name)
            self.assertLessEqual(label[3], box[3]-2, name)
        for name in sorted(set(names), key=len, reverse=True)[:12]:
            blank = a.cocos_ui.render('GetItemUIItemUI', (128, 167), text={'item_name_Text': ''}).convert('RGB')
            filled = a.cocos_ui.render('GetItemUIItemUI', (128, 167), text={'item_name_Text': name}).convert('RGB')
            bbox = ImageChops.difference(blank, filled).getbbox()
            paper = a.cocos_ui.rects['nameBg_Image']
            self.assertIsNotNone(bbox)
            self.assertGreaterEqual(bbox[0], int(paper[0]))
            self.assertLessEqual(bbox[2], round(paper[2]))
        self.open(49, items=[('230001', 1), ('230006', 1)])
        self.save_panel('global-reward-labels')

    def test_all_bag_tabs_are_foreground_and_categories_match_original_item_types(self):
        a = self.app
        a.state.inventory.update({k: 1 for k in a.data.tables['Item']})
        self.open(46)
        expected = {1: {1, 2, 3}, 2: {5}, 3: {6}, 4: {4, 7}, 5: {8}}
        for tab in range(1, 6):
            self.click(f'tag_{tab}_Button')
            page = a.original_page
            self.assertEqual(page.specs[0][2]['z_orders'][f'tag_{tab}_Button'], 100)
            cards = [s for s in page.specs if s[0] == 'BagListItemUI']
            self.assertTrue(cards)
            for spec in cards:
                name = spec[2]['text']['itemName_Text']
                types = {int(r['type']) for r in a.data.tables['Item'].values() if r['name'] == name}
                self.assertTrue(types & expected[tab], (tab, name))
        self.save_panel('global-bag-tabs')

    def test_trial_npc_uses_original_parameter_and_stores_no_fake_ownership(self):
        a = self.app
        key = '600001'
        row = a.data.tables['TrialPet'][key]
        owned = list(a.state.encyclopedia)
        self.open(13, par1=int(key))
        self.assertEqual(a.original_page.specs[0][2]['text']['name_Text'], a.data.tables['Pet'][row['petId']]['name'])
        self.assertEqual(a.original_page.specs[0][2]['text']['lv_BitmapFontLabel'], row['level'])
        self.assertEqual(len(a.original_page.animated_pets), 1)
        self.save_panel('global-trial-npc')
        self.click('trial_Button')
        trial = a.state.pets[-1]
        self.assertEqual((trial.trial_id, trial.trial_remaining), (key, 5))
        self.assertEqual(a.state.encyclopedia, owned)
        self.assertEqual(a.state.active_pet, len(a.state.pets)-1)
        path = a.save_path.parent/'trial-test.json'
        a.state.save(path)
        loaded = GameState.load(a.data.tables, path)
        self.assertEqual(loaded.pets[-1].trial_remaining, 5)
        with self.assertRaises(ValueError): a.state.move_pet(trial.uid, to_bank=True)
        with self.assertRaises(ValueError): a.state.evolve(trial.uid)
        self.open(13, par1=int(key))
        self.save_panel('global-trial-in-use')
        self.click('trial_Button')
        self.assertFalse(any(p.trial_id for p in a.state.pets))
        with self.assertRaises(ValueError): a.state.receive_trial_pet(key)

    def test_trial_has_one_usable_quota_per_participating_battle(self):
        a = self.app
        trial = a.state.receive_trial_pet('600001')
        a.runtime.triggers = []
        for left in range(4, -1, -1):
            b = make_wild_battle(a.data.tables, a.state.pets, next(iter(a.data.tables['VillageEnemy'])), a.state.rng)
            b.player_index = 1
            b.player_active.participated = True
            b.result = 'escape'
            a.battle, a.battle_ui = b, BattleUI(a, b)
            a.finish_battle()
            self.assertEqual(trial.trial_remaining, left)
        b = make_wild_battle(a.data.tables, a.state.pets, next(iter(a.data.tables['VillageEnemy'])), a.state.rng)
        self.assertFalse(next(u for u in b.player if u.pet.uid == trial.uid).alive)

    def test_every_original_trial_npc_has_its_real_species_level_and_preview(self):
        a = self.app
        for key, row in a.data.tables['TrialPet'].items():
            self.open(13, par1=int(key))
            page = a.original_page
            self.assertEqual(page.specs[0][0], 'TrialPetUI', key)
            fields = page.specs[0][2]['text']
            self.assertEqual(fields['lv_BitmapFontLabel'], row['level'], key)
            self.assertEqual(fields['name_Text'], a.data.tables['Pet'][row['petId']]['name'], key)
            self.assertEqual(page.animated_pets[0][0], row['petId'], key)

    def test_lottery_locked_paid_free_and_three_result_pages(self):
        a = self.app
        a.state.functions['8'] = 0
        self.open(68)
        before = copy.deepcopy(a.state.inventory)
        self.click('draw_2_Button')
        self.assertEqual(a.state.inventory, before)
        self.assertIn('开放', a.ui_info.get())
        self.click('confirm_Button')
        a.state.functions['8'] = 1
        self.open(68)
        total = len(a.state.pets+a.state.bank)
        balance = a.state.count('700002')
        self.click('draw_2_Button')
        self.assertEqual(a.state.count('700002'), balance-25)
        self.assertEqual(len(a.state.pets+a.state.bank), total+1)
        self.assertEqual(a.original_page.specs[0][0], 'LuckyDrawPetInfoUI')
        self.save_panel('global-lottery-result')
        self.click('confirm_Button')
        self.assertEqual(a.original_page.specs[0][0], 'LuckyDrawUI')
        balance = a.state.count('700002')
        self.click('draw_3_1_Button')
        self.assertEqual(a.state.count('700002'), balance-50)
        for index in range(3):
            self.assertEqual(a.original_page.specs[0][0], 'LuckyDrawPetInfoUI')
            self.click('confirm_Button')
        self.assertEqual(a.original_page.specs[0][0], 'LuckyDrawUI')
        self.assertEqual(len(a.state.pets+a.state.bank), total+4)
        self.assertTrue(a.state.bank)
        balance = a.state.count('700002')
        self.click('draw_1_Button')
        self.assertEqual(a.state.count('700002'), balance)
        self.assertGreater(a.state.activities['lucky_free_at'], 0)
        self.click('confirm_Button')
        self.click('draw_1_Button')
        self.assertEqual(a.state.count('700002'), balance-10)

    def test_full_lottery_rejects_without_consuming_currency_or_random_state(self):
        s = self.app.state
        s.inventory['700004'], s.inventory['700005'] = len(s.pets), 0
        before, random_state = dict(s.inventory), s.rng.getstate()
        with self.assertRaises(ValueError): Activities(s).draw_pets(3)
        self.assertEqual(before, s.inventory)
        self.assertEqual(random_state, s.rng.getstate())

    def test_capture_confirm_uses_actual_canvas_and_returns_to_map_once(self):
        a = self.app
        a.runtime.triggers = []
        self.root.attributes('-alpha', 0)
        self.root.deiconify()
        self.root.update()
        for item in ['220004', '220005', '220006']:
            a.state.inventory[item] = 1
            before = len(a.state.pets+a.state.bank)
            b = make_wild_battle(a.data.tables, a.state.pets, next(iter(a.data.tables['VillageEnemy'])), a.state.rng)
            b.capture_chance = lambda key: 100
            ui = BattleUI(a, b)
            a.battle, a.battle_ui = b, ui
            ui.selected = {'id': item, 'kind': 'ball'}
            ui._action('confirm_yes')
            ui.advance(seconds=1)
            a.make_frame()
            a.on_click(SimpleNamespace(x=1, y=1))
            self.assertIs(a.battle, b)
            rect = ui.hits['result_continue']
            a.canvas.event_generate('<Button-1>', x=round((rect[0]+rect[2])/2), y=round((rect[1]+rect[3])/2))
            self.root.update()
            self.assertIsNone(a.battle)
            self.assertEqual(len(a.state.pets+a.state.bank), before+1)
            self.assertEqual(a.state.count(item), 0)

    def test_full_storage_cannot_strand_a_caught_result_or_consume_ball(self):
        a = self.app
        a.state.inventory.update({'700004': len(a.state.pets), '700005': 0, '220006': 1})
        b = make_wild_battle(a.data.tables, a.state.pets, next(iter(a.data.tables['VillageEnemy'])), a.state.rng)
        ui = BattleUI(a, b)
        ui.selected = {'id': '220006', 'kind': 'ball'}
        state = a.state.rng.getstate()
        ui._action('confirm_yes')
        self.assertIsNone(b.result)
        self.assertEqual(a.state.count('220006'), 1)
        self.assertEqual(state, a.state.rng.getstate())
        self.assertIn('已满', ui.notice)

    def test_opening_npc_panel_replaces_old_dialogue_on_main_canvas(self):
        a = self.app
        a.dialogue = '尼尔:这段旧对话不能留在弹窗周围。'
        old = a.make_frame().copy()
        a.frame = old
        a.dialogue = None
        self.open(13, par1=600001)
        self.assertIsNotNone(ImageChops.difference(old.convert('RGB'), a.frame.convert('RGB')).getbbox())
        fresh = a.make_frame()
        self.assertIsNone(ImageChops.difference(fresh.convert('RGB'), a.frame.convert('RGB')).getbbox())


if __name__ == '__main__':
    unittest.main(verbosity=2)
