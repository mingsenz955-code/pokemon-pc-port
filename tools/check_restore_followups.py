"""Reported evolution, login, treasure, chest and achievement interactions."""
import json
import time
import unittest
from unittest.mock import patch
from PIL import ImageTk
import check_single_window_flows as base
from achievements import Achievements
from continuous_login import ContinuousLogin
from treasure import TreasureHunt


class FollowupChecks(unittest.TestCase):
    setUp = base.SingleWindowChecks.setUp
    tearDown = base.SingleWindowChecks.tearDown
    open = base.SingleWindowChecks.open
    click = base.SingleWindowChecks.click
    save_panel = base.SingleWindowChecks.save_panel

    def test_panel_corners_do_not_darken_scene(self):
        for ui in [11, 12, 24, 46, 47, 55]:
            self.open(ui)
            label = self.app.ui_art_label
            actual = ImageTk.getimage(label.composited_image)
            for point in [(0, 0), (799, 0), (0, 479), (799, 479)]:
                self.assertEqual(actual.getpixel(point), label.backdrop.getpixel(point), (ui, point))

    def test_pikachu_achievement_claim_once_and_star_quality_are_distinct(self):
        a = self.app
        api = Achievements(a.state)
        self.assertEqual(api.status('101'), 'ready')
        self.open(45)
        self.click('receive_Button')
        self.assertEqual(a.original_page.specs[0][0], 'GetItemUI')
        self.click('confirm_Button')
        self.save_panel('followup-achievement')
        self.assertEqual(api.status('101'), 'claimed')
        with self.assertRaises(ValueError): api.claim('101')
        species = next(k for k, r in a.data.tables['Pet'].items() if r['starLevel'] == '5')
        for _ in range(5):
            pet = a.state.add_generated_pet(species)
            pet.quality = 1
        self.assertEqual(api.status('601'), 'ready')

    def test_login_claimed_day_stays_selected_and_tomorrow_is_distinct(self):
        a = self.app
        ContinuousLogin(a.state).claim()
        before = dict(a.state.inventory)
        self.open(12)
        cards = [s for s in a.original_page.specs if s[0] == 'ContinuousLoginItemUI']
        day1 = next(s for s in cards if s[2]['text']['day_BitmapFontLabel'] == '1')
        day2 = next(s for s in cards if s[2]['text']['day_BitmapFontLabel'] == '2')
        self.assertTrue(day1[2]['visible']['received_Image'])
        self.assertTrue(day1[2]['visible']['selected_Image'])
        self.assertFalse(day2[2]['visible']['wait_Image'])
        self.save_panel('followup-login')
        a.ui_action_for(next(k for k in a.ui_actions if k.startswith('login_1/')))()
        self.assertIn('明日', a.ui_info.get())
        self.assertEqual(before, a.state.inventory)

    def test_evolution_material_gate_and_real_result(self):
        a = self.app
        pet = a.state.pets[0]
        original = pet.species
        row = a.data.tables['Evolution'][original]
        self.open(61, uid=pet.uid)
        self.assertEqual(a.original_page.specs[0][0], 'EvolutionConditionUI')
        self.save_panel('followup-evolution-conditions')
        self.click('evolution_Button')
        self.assertEqual(pet.species, original)
        self.click('confirm_Button')
        pet.level = int(row['level'])
        for key, count in zip(row['itemIds'].split(','), row['itemCounts'].split(',')):
            a.state.inventory[key] = int(count)
        self.open(61, uid=pet.uid)
        self.click('evolution_Button')
        self.assertEqual(pet.species, row['petId'])
        self.assertEqual(a.original_page.specs[0][0], 'PetEvolutionEffectUI')
        self.save_panel('followup-evolution-result')

    def test_buy_map_grants_three_magnifiers_and_real_clue(self):
        a = self.app
        before = a.state.count('700002')
        self.open(24)
        self.assertEqual(a.original_page.specs[0][0], 'TreasureBuyConfirmUI')
        self.save_panel('followup-treasure-buy')
        old = a.state.count('220007')
        self.click('buy_Button')
        self.assertEqual(a.state.count('700002'), before-5)
        self.assertEqual(a.state.count('220007'), old+3)
        self.click('confirm_Button')
        self.assertEqual(a.original_page.specs[0][0], 'TreasureCheckUI')
        self.assertEqual(TreasureHunt(a.state).active()['name'], '镇东树林')
        self.assertIn('itemIcon_2_7', a.original_page.specs[0][2]['resources']['icon_Image'])
        self.save_panel('followup-treasure-check')

    def test_chest_uses_key_icon_and_required_count_not_owned_count(self):
        a = self.app
        a.state.inventory.update({'210001': 1, '240001': 5})
        self.open(55)
        spec = a.original_page.specs[0][2]
        self.assertEqual(spec['text']['need_BitmapFontLabel'], 'x1')
        self.assertIn('itemIcon_4_1', spec['resources']['icon_Sprite'])
        self.save_panel('followup-chest')
        rewards = a.data.tables['ChestItem']['210001']['itemIds'].split(',')
        index = next(i for i, key in enumerate(rewards) if key != '240001')
        with patch.object(a.state.rng, 'choices', return_value=[index]):
            self.click('confirm_Button')
        self.assertEqual(a.state.count('210001'), 0)
        self.assertEqual(a.state.count('240001'), 4)
        self.assertEqual(a.original_page.specs[0][0], 'GetItemUI')

    def test_animated_page_upload_does_not_read_pixels_back_from_tk(self):
        a = self.app
        self.open(12)
        samples = []
        with patch('PIL.ImageTk.getimage', side_effect=AssertionError('Tk pixel readback on animation')):
            for _ in range(8):
                started = time.perf_counter()
                a.original_page.animate()
                samples.append((time.perf_counter()-started)*1000)
        base.fixtures.OUT.joinpath('followup-login-times.json').write_text(json.dumps(samples), encoding='utf-8')


if __name__ == '__main__':
    unittest.main(verbosity=2)
