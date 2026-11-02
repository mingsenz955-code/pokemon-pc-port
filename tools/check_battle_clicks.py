"""Exercise canvas events against real recovered menus, not direct _action calls."""
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from pc_game import NativeGame


class BattleClickChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saves = tempfile.TemporaryDirectory()
        cls.previous_save = os.environ.get('POCKET_NATIVE_SAVE_DIR')
        os.environ['POCKET_NATIVE_SAVE_DIR'] = cls.saves.name
        cls.root = tk.Tk()
        cls.errors = []
        cls.root.report_callback_exception = lambda *error: cls.errors.append(error)
        cls.app = NativeGame(cls.root, OriginalData(ROOT/'original-1.20.4'))
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()
        cls.saves.cleanup()
        if cls.previous_save is None:
            os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
        else:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = cls.previous_save

    def setUp(self):
        app = self.app
        app.runtime.sequence, app.runtime.file, app.runtime.pending = [], '', None
        app.runtime_error, app.dialogue, app.display_request, app.pending_wait = '', None, None, None
        app.battle, app.battle_ui = None, None
        app.state.initialize(2)
        app.start_battle(1002011)
        self.ui = app.battle_ui
        self.ui.render()

    def click(self, key, targets=False):
        self.ui.render()
        rect = (self.ui.target_hits if targets else self.ui.hits)[key]
        x, y = round((rect[0]+rect[2])/2), round((rect[1]+rect[3])/2)
        self.app.canvas.event_generate('<Button-1>', x=x, y=y)
        self.root.update()
        self.assertFalse(self.errors, self.errors)

    def test_original_pet_targets_open_different_menus(self):
        self.click('mineMenuPos_Panel', targets=True)
        self.assertEqual(self.ui.screen, 'commands')
        self.click('enemyMenuPos_Panel', targets=True)
        self.assertEqual(self.ui.screen, 'skills')

    def test_hp_energy_bag_and_pet_buttons(self):
        for key, expected, filter_value in [('hp_Button', 'items', 1),
                                            ('energy_Button', 'items', 2),
                                            ('bag_Button', 'items', None),
                                            ('pet_Button', 'pets', None)]:
            self.ui.screen = 'commands'
            self.click(key)
            self.assertEqual(self.ui.screen, expected, key)
            if expected == 'items':
                self.assertEqual(self.ui.item_filter, filter_value)

    def test_normal_attack_advances_real_battle(self):
        self.ui.screen = 'skills'
        before = self.app.battle.round
        self.click('attack_Button')
        self.assertGreater(self.app.battle.round, before)

    def test_skill_info_does_not_attack_and_dismisses(self):
        self.ui.screen = 'skills'
        before = self.app.battle.round
        self.click('skillInfo_Button_1')
        self.assertTrue(self.ui.info)
        self.assertEqual(self.app.battle.round, before)
        self.app.canvas.event_generate('<Button-1>', x=500, y=200)
        self.root.update()
        self.assertFalse(self.ui.info)

    def test_skill_button_executes_instead_of_silent_refresh(self):
        self.ui.screen = 'skills'
        before = self.app.battle.round
        self.click('skillMenu_1_Button')
        self.assertGreater(self.app.battle.round, before)

    def test_same_animation_sample_reuses_rendered_image(self):
        with patch('battle_ui.time.monotonic', return_value=self.ui.animation_clock+.001):
            frame = self.ui.render()
            self.assertIs(frame, self.ui.render())
        self.click('enemyMenuPos_Panel', targets=True)
        self.assertIsNot(frame, self.ui.render())

    def test_single_item_is_clickable_and_confirmation_consumes_once(self):
        item = next(key for key, effect in self.app.data.tables['PetItem'].items()
                    if int(effect['type']) == 1 and str(effect['parameters']).startswith('1,')
                    and int(self.app.data.tables['Item'][key]['useType']) in (1, 2))
        self.app.state.inventory = {item: 2}
        self.app.battle.player_active.hp = 1
        self.ui.screen, self.ui.item_filter = 'items', 1
        self.click('itemMenu_1_Button')
        self.assertEqual(self.ui.screen, 'confirm')
        self.click('confirm_yes')
        self.assertEqual(self.app.state.count(item), 1)

    def test_switch_click_changes_active_pet(self):
        self.ui.screen = 'pets'
        self.click('pet_1')
        self.assertEqual(self.app.battle.player_index, 1)

    def test_forced_switch_uses_pet_list(self):
        self.app.battle.force_switch = True
        self.click('enemyMenuPos_Panel', targets=True)
        self.assertEqual(self.ui.screen, 'pets')
        self.click('pet_1')
        self.assertFalse(self.app.battle.force_switch)

    def test_render_evidence(self):
        folder = ROOT/'outputs/verification/battle-clicks'
        folder.mkdir(parents=True, exist_ok=True)
        for screen in ('main', 'commands', 'skills', 'pets'):
            self.ui.screen = screen
            self.ui.render().save(folder/(screen+'.png'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
