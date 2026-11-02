"""Real page hit dispatch, all item rows, and reward effects using isolated saves."""
import copy
import os
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from pc_game import NativeGame
from event_runtime import Request
from game_state import GameState
from battle import make_wild_battle
from battle_ui import BattleUI
from particles import draw_emitter

DATA = OriginalData(ROOT/'original-1.20.4')
OUT = ROOT/'outputs/verification/inventory-interactions'
OUT.mkdir(parents=True, exist_ok=True)


class InventoryChecks(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.prior = os.environ.get('POCKET_NATIVE_SAVE_DIR')
        os.environ['POCKET_NATIVE_SAVE_DIR'] = self.folder.name
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = NativeGame(self.root, DATA)
        a = self.app
        a.runtime.file, a.runtime.sequence, a.runtime.pending = '', [], None
        a.display_request, a.dialogue, a.pending_wait = None, None, None
        a.state.initialize(1)
        a.state.add_preset(1)
        a.guide.rebind(a.state)
        a.state.inventory.update({'700001': 100000, '700002': 1000})

    def tearDown(self):
        if self.app.ui_window and self.app.ui_window.winfo_exists():
            self.app.ui_window.destroy()
        for job in self.root.tk.call('after', 'info'):
            self.root.after_cancel(job)
        self.root.destroy()
        self.folder.cleanup()
        if self.prior is None:
            os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
        else:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = self.prior

    def open(self, uiid, **parameters):
        self.app.open_ui(Request('openui', 'test', 1, {'parameters': {'uiid': uiid, **parameters}}))
        if self.app.ui_window:
            self.app.ui_window.withdraw()

    def click(self, key, xoffset=None):
        a = self.app
        r = a.ui_buttons.get(key) or a.ui_hits[key]
        e = SimpleNamespace(x=r[0]+xoffset if xoffset is not None else (r[0]+r[2])/2,
                            y=(r[1]+r[3])/2)
        a.on_ui_press(e)
        a.on_ui_release(e)

    def test_bag_icon_click_selects_row_and_real_use_button(self):
        a = self.app
        a.state.inventory = {'230010': 2, '230011': 2}
        self.open(46)
        self.click('bag_row_1', 42)
        self.assertIn('等级', a.ui_info.get())
        self.click(next(k for k in a.ui_buttons if k.endswith('/use_Button')))
        self.assertEqual('PetSelectUI', a.original_page.specs[0][0])
        level = a.state.pets[0].level
        self.click('pet_select_0', 42)
        self.assertEqual(level+5, a.state.pets[0].level)
        self.assertEqual(1, a.state.count('230011'))
        a.ui_base_layer.save(OUT/'bag.png')

    def test_all_pet_item_effects_and_no_effect_rollback(self):
        for key, row in DATA.tables['PetItem'].items():
            s = GameState(DATA.tables, 57)
            s.initialize(1)
            p = s.add_preset(1)
            p.level, p.friendly, p.hp, p.energy = 10, 0, 1, 1
            s.inventory[key] = 2
            if row['type'] == '3':
                p.hp = 0
            if DATA.tables['Item'][key]['useType'] == '3':
                before = s.payload()
                with self.assertRaises(ValueError):
                    s.use_item(key, p)
                self.assertEqual(before, s.payload())
                continue
            s.use_item(key, p)
            self.assertEqual(1, s.count(key), key)
        s, p = self.app.state, self.app.state.pets[0]
        s.inventory['230010'], p.friendly = 2, 6
        with self.assertRaises(ValueError):
            s.use_item('230010', p)
        self.assertEqual(2, s.count('230010'))

    def test_all_skill_scrolls_teach_the_table_skill_once(self):
        for key, row in DATA.tables['SkillItem'].items():
            s = GameState(DATA.tables, 58)
            s.initialize(1)
            p = s.add_preset(1)
            p.skills, p.talents = [], []
            s.inventory[key] = 2
            s.learn_skill(p.uid, row['skillId'], scroll=key)
            self.assertIn(str(row['skillId']), p.skills+p.talents)
            self.assertEqual(1, s.count(key))
            with self.assertRaises(ValueError):
                s.learn_skill(p.uid, row['skillId'], scroll=key)
            self.assertEqual(1, s.count(key))

    def test_every_item_description_stays_inside_original_text_rectangle(self):
        ui = self.app.cocos_ui
        base = ui.render('BagUI', text={'info_Text': ''})
        bounds = ui.rects['info_Text']
        for key, row in DATA.tables['Item'].items():
            image = ui.render('BagUI', text={'info_Text': row['des']})
            box = ImageChops.difference(base.convert('RGB'), image.convert('RGB')).getbbox()
            if box:
                self.assertGreaterEqual(box[0], int(bounds[0])-1, key)
                self.assertGreaterEqual(box[1], int(bounds[1])-1, key)
                self.assertLessEqual(box[2], int(bounds[2])+1, key)
                self.assertLessEqual(box[3], int(bounds[3])+1, key)

    def test_known_encyclopedia_card_opens_from_its_icon(self):
        self.app.state.encyclopedia = sorted(DATA.tables['Pet'], key=int)
        self.open(48)
        self.click('illustrated_card_0', 45)
        self.assertEqual('IllustratedPetInfoUI', self.app.original_page.specs[0][0])
        self.app.ui_base_layer.save(OUT/'illustrated-detail.png')

    def test_login_claim_shows_original_particle_and_cannot_repeat(self):
        self.open(12)
        a = self.app
        row = DATA.tables['ContinuousLogin']['1']
        before = a.state.count(row['rewardKid'])
        key = next(k for k in a.ui_buttons if k.startswith('login_0/') and k.endswith('/get_Button'))
        self.click(key)
        self.assertTrue(a.reward_visible)
        self.assertTrue(any(p[0].endswith('lizi_2.plist') for p in a.original_page.particles))
        a.original_page.animate()
        a.ui_base_layer.save(OUT/'reward.png')
        self.assertEqual(before+int(row['rewardCount']), a.state.count(row['rewardKid']))
        self.click(next(k for k in a.ui_buttons if k.endswith('/confirm_Button')))
        a.ui_actions['get_Button']()
        self.assertEqual(before+int(row['rewardCount']), a.state.count(row['rewardKid']))

    def test_particle_uses_original_texture_and_changes_over_time(self):
        path = DATA.assets/'res/UI/lizi/lizi_2.plist'
        a, b = [Image.new('RGBA', (200, 200), 'black') for _ in range(2)]
        draw_emitter(a, path, (100, 100), (.42, .42), .2)
        draw_emitter(b, path, (100, 100), (.42, .42), .6)
        self.assertIsNotNone(ImageChops.difference(a, b).convert('RGB').getbbox())

    def test_pet_details_use_original_rows_with_scrollable_description(self):
        a = self.app
        a.state.pets[0].talents = list(DATA.tables['Talent'])[:2]
        self.open(57, uid=a.state.pets[0].uid)
        self.assertTrue(any(s[0] == 'PetListSkillItemUI' for s in a.original_page.specs))
        self.click(next(k for k in a.ui_buttons if k.endswith('/talentTag_Button')))
        self.assertTrue(a.pet_description['text'])
        a.ui_base_layer.save(OUT/'pet-detail.png')

    def test_lottery_and_gold_store_use_original_pages(self):
        a = self.app
        self.open(68)
        self.assertEqual('LuckyDrawUI', a.original_page.specs[0][0])
        before = len(a.state.pets)+len(a.state.bank)
        a.state.functions['8'] = 1
        self.click(next(k for k in a.ui_buttons if k.endswith('/draw_1_Button')))
        self.assertEqual(before+1, len(a.state.pets)+len(a.state.bank))
        self.open(63)
        self.assertEqual('ShopUI', a.original_page.specs[0][0])
        self.assertTrue(any(s[0] == 'ShopGoodsUI' for s in a.original_page.specs))
        a.ui_base_layer.save(OUT/'topup.png')

    def test_all_three_balls_can_be_selected_confirmed_and_consumed(self):
        for ball in ['220004', '220005', '220006']:
            a = self.app
            for pet in a.state.pets:
                pet.hp, pet.energy = pet.stats(DATA.tables)[:2]
            a.state.inventory[ball] = 2
            battle = make_wild_battle(DATA.tables, a.state.pets, next(iter(DATA.tables['VillageEnemy'])), a.state.rng)
            ui = BattleUI(a, battle)
            ui.selected = {'id': ball, 'kind': 'ball'}
            ui.screen = 'confirm'
            ui._action('confirm_yes')
            self.assertEqual(1, a.state.count(ball), ball)
            self.assertTrue(any(e['type'] == 'catch_attempt' for e in battle.events))

    def test_scroll_from_bag_confirms_and_returns_to_bag(self):
        a = self.app
        key, row = next(iter(DATA.tables['SkillItem'].items()))
        a.state.inventory = {key: 2}
        a.state.pets[0].skills, a.state.pets[0].talents = [], []
        self.open(46)
        a.ui_actions['tag_3_Button']()
        a.ui_actions['use_Button']()
        a.ui_actions['pet_select_0']()
        self.assertEqual('SkillLearnConfirmUI', a.original_page.specs[0][0])
        self.click(next(k for k in a.ui_buttons if k.endswith('/confirm_Button')))
        self.assertEqual(1, a.state.count(key))
        self.assertIn(str(row['skillId']), a.state.pets[0].skills+a.state.pets[0].talents)
        self.assertEqual('BagUI', a.original_page.specs[0][0])

    def test_perfumes_replace_original_state_instead_of_stacking(self):
        a = self.app
        for key in ('220002', '220003'):
            a.state.inventory[key] = 2
            a.use_perfume(key)
            self.assertEqual(1, a.state.count(key))
            self.assertEqual(int(DATA.tables['FunctionItem'][key]['parameters'].split(',')[1]), a.state.activities['perfume']['steps'])

    def test_every_item_has_original_icon_and_description(self):
        for key, row in DATA.tables['Item'].items():
            self.assertTrue(row['des'], key)
            self.assertIsNotNone(DATA.image('ItemIcon/'+row['texture']), key)

    def test_seen_but_uncaught_card_opens_without_unlocking_ownership(self):
        a = self.app
        species = min((k for k, r in DATA.tables['Pet'].items() if r['kind'] == '1' and r['open'] == '1'), key=int)
        a.state.encyclopedia = []
        a.state.record_seen_pet(species)
        self.open(48)
        self.click('illustrated_card_0', 45)
        self.assertEqual('IllustratedPetInfoUI', a.original_page.specs[0][0])
        self.assertEqual([], a.state.encyclopedia)

    def test_starting_battle_records_only_active_opponent_as_seen(self):
        a = self.app
        before, owned = set(a.state.seen_species), list(a.state.encyclopedia)
        a.start_battle('511051')
        self.assertEqual(before | {a.battle.enemy_active.pet.species}, set(a.state.seen_species))
        self.assertEqual(owned, a.state.encyclopedia)

    def test_treasure_search_uses_camera_and_original_radar(self):
        from treasure import TreasureHunt
        a = self.app
        a.state.inventory['700002'] = 50
        entry = TreasureHunt(a.state).buy('1')
        a.load_map(7401)
        self.assertFalse(a.search_treasure())
        self.assertEqual('没有发现宝藏！', a.treasure_search_fx['text'])
        self.assertFalse(entry['revealed'])
        a.load_map(entry['map_id'], entry['x'], entry['y'])
        self.assertTrue(a.search_treasure())
        self.assertEqual('恭喜您发现宝藏！', a.treasure_search_fx['text'])
        self.assertEqual(1, a.state.count('220007'))
        a.treasure_search_fx['age'] = .3
        a.screen_black = False
        a.make_frame().save(OUT/'treasure-radar.png')


if __name__ == '__main__':
    unittest.main(verbosity=2)
