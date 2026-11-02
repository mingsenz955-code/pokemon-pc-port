"""Regression coverage for the reported in-game panels and reward blockers."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PIL import ImageChops, ImageTk
import check_inventory_interactions as fixtures
from event_runtime import Request
from activities import Activities
from task_page import TaskPage
from game_overlay import GameOverlay
from task_progress import TaskProgress


class SingleWindowChecks(unittest.TestCase):
    def setUp(self):
        fixtures.InventoryChecks.setUp(self)
        self.app.screen_black = False
        self.app.load_map(101)
    tearDown = fixtures.InventoryChecks.tearDown
    open = fixtures.InventoryChecks.open
    def click(self, key):
        a = self.app
        rect = next(r for k, r in a.ui_hits.items() if k == key or k.endswith('/'+key))
        event = SimpleNamespace(x=(rect[0]+rect[2])/2, y=(rect[1]+rect[3])/2)
        a.on_ui_press(event)
        a.on_ui_release(event)

    def save_panel(self, name):
        ImageTk.getimage(self.app.ui_art_label.composited_image).save(fixtures.OUT/(name+'.png'))

    def test_pet_item_clicks_recover_and_return_without_new_windows(self):
        a = self.app
        pet = a.state.pets[0]
        item = next(k for k, r in a.data.tables['PetItem'].items() if r['type'] == '1' and r['parameters'].startswith('1,'))
        for key in a.data.tables['PetItem']:
            a.state.inventory.pop(key, None)
        a.state.grant(item, 2)
        pet.hp = 1
        self.open(47)
        self.assertIsInstance(a.ui_window, GameOverlay)
        self.click('useItem_Button')
        self.assertEqual(a.original_page.specs[0][0], 'BagUI')
        self.click('use_Button')
        self.assertGreater(pet.hp, 1)
        self.assertEqual(a.state.count(item), 1)
        self.assertEqual(a.original_page.specs[0][0], 'PetListUI')
        self.assertFalse(any(c.winfo_class() == 'Toplevel' for c in self.root.winfo_children()))
        self.save_panel('single-window-pets')

    def test_pet_stand_changes_without_changing_buttons(self):
        self.open(47)
        page = self.app.original_page
        before = dict(page.hits)
        x = page.pet_frame(page.layer.copy(), 0)
        y = page.pet_frame(page.layer.copy(), .32)
        self.assertIsNotNone(ImageChops.difference(x.convert('RGB'), y.convert('RGB')).getbbox())
        self.assertEqual(before, page.hits)

    def test_real_tip_text_replaces_authored_bag_full_placeholder(self):
        a = self.app
        self.open(46)
        a._page_tip('亲密度已满，无法使用！', a.original_page.publish)
        text = a.original_page.specs[0][2]['text']
        self.assertEqual(text['tip_Text'], '亲密度已满，无法使用！')
        self.save_panel('single-window-tip')

    def test_script_grant_yields_popup_and_never_grants_twice(self):
        a = self.app
        runtime = a.runtime
        runtime.file = 'test-reward.json'
        runtime.sequence = [{'id': 1, 'type': 'giveitem', 'parameters': {'itemid': 700001, 'itemcount': 200}},
                            {'id': 2, 'type': 'talk', 'text': '尼尔:谢谢！'}]
        runtime.index = 0
        before = a.state.count('700001')
        a.drive()
        self.assertEqual(runtime.pending.kind, 'reward')
        self.assertEqual(a.original_page.specs[0][0], 'GetItemUI')
        self.assertEqual(a.state.count('700001'), before+200)
        self.save_panel('single-window-reward')
        self.click('confirm_Button')
        self.assertEqual(runtime.pending.kind, 'talk')
        self.assertEqual(a.state.count('700001'), before+200)

    def test_accept_card_has_real_rewards_and_no_duplicate_host_form(self):
        a = self.app
        request = Request('accepttask', 'pEventBTask201.json', 6, {'parameters': {'btask': 201}})
        a.runtime.pending = request
        a.accept_task_ui(request)
        self.assertEqual(a.original_page.specs[0][0], 'AcceptBTaskUI')
        self.assertEqual(sum(s[0] == 'RewardItemUI' for s in a.original_page.specs), 2)
        self.assertEqual(len(a.ui_window.winfo_children()), 2)
        self.save_panel('single-window-accept')
        a._accept_task_finish(True)
        self.assertEqual(a.state.branch_states['201'], 3)

    def test_lottery_full_party_uses_bank_and_true_full_rolls_back(self):
        s = self.app.state
        s.inventory['700004'] = 1
        s.inventory['700005'] = 3
        before = s.count('700002')
        pets = Activities(s).draw_pets(3)
        self.assertEqual(len(pets), 3)
        self.assertEqual(len(s.bank), 3)
        self.assertEqual(s.count('700002'), before-50)
        before = copy.deepcopy(s.inventory)
        with self.assertRaises(ValueError):
            Activities(s).draw_pets(1)
        self.assertEqual(before, s.inventory)
        self.open(68)
        self.save_panel('single-window-lottery')

    def test_treatment_updates_hp_mp_and_consumes_one_free_use(self):
        a = self.app
        pet = a.state.pets[0]
        pet.hp = pet.energy = 1
        a.state.inventory['700006'] = 8
        self.open(11)
        self.save_panel('single-window-heal')
        self.click('confirm_Button')
        stats = pet.stats(a.data.tables)
        self.assertEqual((pet.hp, pet.energy), tuple(stats[:2]))
        self.assertEqual(a.state.count('700006'), 7)
        self.assertIn('已恢复', a.ui_info.get())
        self.click('confirm_Button')
        self.assertFalse(a.ui_open)

    def test_branch_reward_cards_are_inside_paper(self):
        a = self.app
        a.state.branch_states['201'] = 3
        a.state.task_counts['branch:201'] = [0]
        self.open(44, page='branch')
        page = a.task_page
        art = page.render()
        a.make_frame().save(fixtures.OUT/'single-window-task.png')
        x, y, right, bottom = page.hits['rewards']
        self.assertLessEqual(bottom, page.rects['reward_Panel'][3]+1)
        self.assertEqual(page.reward_limit(), 0)

    def test_passive_task_refresh_cannot_complete_zero_count_story_area(self):
        s = self.app.state
        s.main_task, s.main_state = 7, 4  # Repair a previously premature checkmark.
        s.task_counts['main:7'] = [0]
        TaskProgress(s).update()
        self.assertEqual(s.main_state, 3)
        self.assertTrue(s.main_matches(7, 3))
        TaskProgress(s).update('area', 10103)
        self.assertEqual(s.main_state, 4)

    def test_capture_replays_native_clip_before_failed_enemy_attack(self):
        from battle import make_wild_battle
        from battle_ui import BattleUI
        a = self.app
        battle = make_wild_battle(a.data.tables, a.state.pets, next(iter(a.data.tables['VillageEnemy'])), a.state.rng)
        ui = BattleUI(a, battle)
        battle.capture_chance = lambda key: 1
        with patch.object(battle.rng, 'randrange', return_value=99):
            battle._attempt_catch('220004')
        ui._capture_events()
        self.assertEqual(ui.anim['capture_clip'], 'Animation7')
        self.assertTrue(ui.anim_queue)
        ui.advance(seconds=1.4)
        ui.render().save(fixtures.OUT/'single-window-capture.png')
        self.assertEqual(ui.anim['kind'], 'capture')
        ui.advance(seconds=2.11)
        self.assertIn(ui.anim['kind'], ('attack', 'skill'))

    def test_original_bank_nurse_event_resumes_after_treatment(self):
        a = self.app
        a.load_map(5805)
        self.assertEqual(a.map.info['name'], '斯塔镇银行')
        pet = a.state.pets[0]
        pet.hp = 1
        a.runtime.start('pEventTalk580504.json', npc_id=580504)
        a.drive()
        self.assertIn('宠物护士', a.dialogue)
        a.make_frame().save(fixtures.OUT/'single-window-nurse.png')
        a.interact()
        self.assertEqual(a.ui_parameters['uiid'], 11)
        self.click('confirm_Button')
        self.assertFalse(a.ui_open)
        self.assertEqual(pet.hp, pet.stats(a.data.tables)[0])
        self.assertIn('宠物们已经痊愈了', a.dialogue)

    def test_longest_task_descriptions_only_change_the_inset_viewport(self):
        a = self.app
        for category, table in [('main', 'MainTask'), ('branch', 'BranchTask')]:
            longest = sorted(a.state.tables[table], key=lambda k: len(a.state.tables[table][k]['des']), reverse=True)[:3]
            for key in longest:
                if category == 'main':
                    a.state.main_task, a.state.main_state = int(key), 3
                else:
                    a.state.branch_states = {key: 3}
                page = TaskPage(a, category)
                row = a.state.tables[table][key]
                text = row['des']
                try:
                    row['des'] = ''
                    before = page.render().convert('RGB')
                    row['des'] = text
                    after = page.render().convert('RGB')
                    bounds = ImageChops.difference(before, after).getbbox()
                    rect = page.hits['description']
                    self.assertIsNotNone(bounds, key)
                    self.assertGreaterEqual(bounds[0], int(rect[0]))
                    self.assertGreaterEqual(bounds[1], int(rect[1]))
                    self.assertLessEqual(bounds[2], round(rect[2]))
                    self.assertLessEqual(bounds[3], round(rect[3]))
                finally:
                    row['des'] = text

    def test_reward_popup_restores_legacy_panel_callbacks(self):
        a = self.app
        self.open(50, text='确定打开宝箱？')
        original = dict(a.ui_actions)
        a.show_reward('获得金币', [('700001', 200)])
        self.assertEqual(a.original_page.specs[0][0], 'GetItemUI')
        self.click('confirm_Button')
        self.assertIsNone(a.original_page)
        self.assertEqual(a.ui_actions, original)


if __name__ == '__main__':
    unittest.main(verbosity=2)
