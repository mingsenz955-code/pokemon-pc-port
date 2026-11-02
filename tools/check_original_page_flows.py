"""Isolated, withdrawn-window flows; never reads or changes the player's save."""
import copy
import os
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import ImageChops

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from pc_game import NativeGame
from original_data import OriginalData
from game_state import GameState
from event_runtime import Request
from battle import Battle
from battle_ui import BattleUI
from csb_render import CocosUI
from area_map import region_image, region_for, parent_map

DATA = OriginalData(ROOT/'original-1.20.4')
OUTPUT = ROOT/'outputs/verification/original-page-audit'
OUTPUT.mkdir(parents=True, exist_ok=True)


class PageFlows(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = os.environ.get('POCKET_NATIVE_SAVE_DIR')
        os.environ['POCKET_NATIVE_SAVE_DIR'] = self.temp.name
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = NativeGame(self.root, DATA)
        self.app.runtime.file, self.app.runtime.sequence, self.app.runtime.pending = '', [], None
        self.app.state.add_preset(1)
        self.app.state.grant('700001', 50000)
        self.app.load_map(101, 1248, 1504)

    def tearDown(self):
        if self.app.ui_window and self.app.ui_window.winfo_exists():
            self.app.ui_window.destroy()
        for job in self.root.tk.call('after', 'info'):
            self.root.after_cancel(job)
        self.root.destroy()
        self.temp.cleanup()
        if self.previous is None:
            os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
        else:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = self.previous

    def open(self, uid):
        self.app.open_ui(Request('openui', 'test', 1, {'parameters': {'uiid': uid}}))
        self.app.ui_window.withdraw()
        self.root.update()

    def click(self, key):
        app = self.app
        r = app.ui_buttons.get(key) or app.ui_hits[key]
        event = SimpleNamespace(x=(r[0]+r[2])/2, y=(r[1]+r[3])/2)
        app.on_ui_press(event)
        app.on_ui_release(event)

    def test_shop_selection_hover_and_real_purchase(self):
        self.open(1)
        app = self.app
        key = next(k for k in app.ui_buttons if k.startswith('shop_goods_0/') and k.endswith('/buy_Button'))
        first = app.original_page.specs[1]
        self.assertEqual(('ShopGoodsUI', (153, 233)), first[:2])
        # Hover feedback may only affect the button, never discard the dynamic
        # goods, current currencies or other cards.
        r = app.ui_buttons[key]
        before = app.ui_base_layer.copy()
        after = app.original_page.feedback(key)
        difference = ImageChops.difference(before, after).convert('RGB').getbbox()
        if difference:
            self.assertGreaterEqual(difference[0], int(r[0])-1)
            self.assertLessEqual(difference[2], int(r[2])+1)
        self.click(key)
        self.assertEqual('BuyConfirmUI', app.ui_render_args['name'])
        rowkey, row = sorted(DATA.tables['Shop'].items(), key=lambda p: int(p[0]))[0]
        before_count, before_money = app.state.count(row['goodsKid']), app.state.count(row['moneyType'])
        app.ui_actions['right_Button']()
        app.ui_actions['confirm_Button']()
        self.assertEqual(before_count+2*int(row.get('gotCount', 1)), app.state.count(row['goodsKid']))
        self.assertEqual(before_money-2*int(row['price']), app.state.count(row['moneyType']))
        app.ui_base_layer.save(OUTPUT/'shop.png')

    def test_bag_uses_selected_pet_and_clears_scroll_hits(self):
        app = self.app
        app.state.inventory = {'700001': 50000, '230003': 3}
        for pet in app.state.pets:
            pet.hp = 1
        self.open(46)
        # Select the potion by its original row's icon binding.
        index = next(int(spec[4].split('_')[1].split('/')[0]) for spec in app.original_page.specs[1:]
                     if spec[2].get('resources', {}).get('icon_Image') == 'ItemIcon/'+DATA.tables['Item']['230003']['texture'])
        app.ui_actions[f'bag_row_{index}']()
        app.ui_actions['use_Button']()
        self.assertTrue(any(k.startswith('pet_select_') for k in app.ui_hits))
        pet = app.state.pets[0]
        app.ui_actions['pet_select_0']()
        self.assertGreater(pet.hp, 1)
        self.assertEqual(2, app.state.count('230003'))
        app.ui_base_layer.save(OUTPUT/'bag.png')

    def test_hatch_picker_can_choose_second_egg(self):
        app = self.app
        keys = sorted(DATA.tables['HatchItem'], key=int)[:2]
        for key in keys:
            app.state.grant(key, 1)
        self.open(5)
        app.ui_actions['putIn_Button']()
        self.assertIn('bag_row_1', app.ui_actions)
        app.ui_actions['bag_row_1']()
        app.ui_actions['use_Button']()
        self.assertEqual(keys[1], app.state.activities['eggs']['0']['item'])
        self.assertEqual(1, app.state.count(keys[0]))
        self.assertEqual(0, app.state.count(keys[1]))

    def test_login_claim_and_state_art_do_not_repeat_rewards(self):
        app = self.app
        self.open(12)
        row = DATA.tables['ContinuousLogin']['1']
        before = app.state.count(row['rewardKid'])
        key = next(k for k in app.ui_buttons if k.startswith('login_0/') and k.endswith('/get_Button'))
        self.click(key)
        self.assertEqual(before+int(row['rewardCount']), app.state.count(row['rewardKid']))
        self.assertTrue(app.reward_visible)
        app.ui_actions['confirm_Button']()
        self.click(key)
        self.assertEqual(before+int(row['rewardCount']), app.state.count(row['rewardKid']))
        app.ui_actions['confirm_Button']()
        spec = next(s for s in app.original_page.specs if s[4] == 'login_0/')
        self.assertTrue(spec[2]['visible']['received_Image'])
        app.ui_base_layer.save(OUTPUT/'login.png')

    def test_encyclopedia_five_columns_and_unknown_pet_is_not_revealed(self):
        self.open(48)
        app = self.app
        cards = [s for s in app.original_page.specs if s[0] == 'IllustratedItemUI']
        self.assertEqual((115, 113), cards[0][1])
        self.assertEqual(cards[0][3][1], cards[4][3][1])
        self.assertGreater(cards[5][3][1], cards[0][3][1])
        # Unknown cards should not open a species dossier or reveal its name.
        unknown = next(s for s in cards if s[2]['visible']['none_Image'])
        key = 'illustrated_card_'+unknown[4].split('_')[1].split('/')[0]
        app.ui_actions[key]()
        self.assertEqual('IllustratedUI', app.ui_render_args['name'])
        app.ui_base_layer.save(OUTPUT/'illustrated.png')
        key = str(app.state.pets[0].species)
        app.open_ui(Request('openui', 'known-pet', 1, {'parameters': {'uiid': 8, 'species': key}}))
        before = app.ui_base_layer.copy()
        app.ui_actions['check_Button']()
        self.assertTrue(app.ui_open, '查看 must toggle the dossier, not close it')
        self.assertIsNotNone(ImageChops.difference(before, app.ui_base_layer).convert('RGB').getbbox())
        self.assertIn('infoTitle_1_Text', app.ui_rects)
        app.ui_base_layer.save(OUTPUT/'illustrated-detail.png')

    def test_achievement_tiers_and_native_rewards_are_visible(self):
        self.open(45)
        app = self.app
        cards = [s for s in app.original_page.specs if s[0] == 'AchievementItemUI']
        self.assertTrue(cards)
        self.assertEqual((655, 164), cards[0][1])
        self.assertNotEqual('', cards[0][2]['text']['name_Text'])
        self.assertTrue(any(s[0] == 'RewardItemUI' for s in app.original_page.specs))
        area = app.ui_rects['item_ScrollView']
        for key, r in app.ui_hits.items():
            if key.startswith('achievement_'):
                self.assertGreaterEqual(r[1], area[1])
                self.assertLessEqual(r[3], area[3])
        app.ui_base_layer.save(OUTPUT/'achievement.png')

    def test_area_map_uses_tmx_and_world_has_both_original_pages(self):
        app = self.app
        self.assertEqual('1', region_for(DATA, 5807))
        self.assertEqual('101', parent_map(DATA, 5807))
        self.open(9)
        image, boxes = region_image(app, '1')
        self.assertEqual((690, 541, 882, 669), boxes['101'])
        self.assertEqual((1408, 1088), image.size)
        before = app.ui_base_layer.copy()
        app.page_drag(-100, 0)
        self.assertIsNotNone(ImageChops.difference(before, app.ui_base_layer).convert('RGB').getbbox())
        app.ui_base_layer.save(OUTPUT/'area.png')
        app.ui_actions['worldMap_Button']()
        self.assertEqual('WorldMap1UI', app.original_page.specs[0][0])
        app.ui_base_layer.save(OUTPUT/'world-1.png')
        app.page_drag(-50, 0)
        self.assertEqual('WorldMap2UI', app.original_page.specs[0][0])
        app.ui_base_layer.save(OUTPUT/'world-2.png')

    def test_wild_save_load_preserves_random_state_and_encounter(self):
        app = self.app
        app.load_map(804)
        self.assertGreater(app.encounter_threshold, 0)
        self.assertTrue(app.save())
        before = app.state.rng.getstate()
        threshold = app.encounter_threshold
        self.assertTrue(app.restore())
        self.assertEqual(before, app.state.rng.getstate())
        self.assertEqual(threshold, app.encounter_threshold)


class Effects(unittest.TestCase):
    def test_original_attack_frame_and_effect_length(self):
        state = GameState(DATA.tables, 42)
        pet = copy.deepcopy(state.pets[0])
        pet.talents = []
        enemy = copy.deepcopy(pet)
        enemy.uid = 'enemy'
        battle = Battle(DATA.tables, [pet], [enemy], state.rng)
        for unit in battle.player+battle.enemy:
            unit.hp = unit.max_hp = 10000
        app = SimpleNamespace(data=DATA, state=state, cocos_ui=CocosUI(DATA), battle_tips=[])
        ui = BattleUI(app, battle)
        battle._attack(battle.player_active, battle.enemy_active)
        ui._capture_events()
        self.assertAlmostEqual(26*25/60, ui.anim['duration'])
        self.assertAlmostEqual(5*25/60, ui.anim['hit_at'])
        key = ('enemy', enemy.uid)
        ui.advance(ui.anim['hit_at']-.01)
        self.assertEqual(10000, ui.visual_hp[key])
        ui.advance(.02)
        self.assertLess(ui.visual_hp[key], 10000)
        ui.render().save(OUTPUT/'battle-hit.png')
        self.assertIn('p_center', ui.pet_bones['enemy'])
        plan = ui.effects.plan('300001', 'player')
        self.assertAlmostEqual(101*25/60, plan['duration'])
        a = DATA.armature(plan['path'], 'Animation1', 2)
        b = DATA.armature(plan['path'], 'Animation1', 10)
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertNotEqual(a.tobytes(), b.tobytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
