"""Purchase receipts, legacy ownership, visible buttons and six carried slots."""
import copy
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from pathlib import Path
import check_single_window_flows as fixtures
from game_state import GameState

class TrialChecks(unittest.TestCase):
    setUp = fixtures.SingleWindowChecks.setUp
    tearDown = fixtures.SingleWindowChecks.tearDown
    open = fixtures.SingleWindowChecks.open

    def test_purchase_once_and_reopen_hides_buttons(self):
        a=self.app; key=next(iter(a.data.tables['TrialPet']))
        a.state.inventory['700001']=10000000
        trial=a.state.receive_trial_pet(key)
        pet=a.state.buy_trial_pet(key)
        self.assertIs(pet,trial)
        before=a.state.payload()
        with self.assertRaises(ValueError): a.state.buy_trial_pet(key)
        with self.assertRaises(ValueError): a.state.receive_trial_pet(key)
        self.assertEqual(a.state.payload(),before)
        self.open(13,par1=key)
        self.assertFalse(any(k.endswith('/buy_Button') or k.endswith('/trial_Button') for k in a.ui_hits))
        a.state.save(a.save_path)
        loaded=GameState.load(a.data.tables,a.save_path)
        before=loaded.payload()
        with self.assertRaises(ValueError): loaded.buy_trial_pet(key)
        self.assertEqual(loaded.payload(),before)

    def test_direct_purchase_bank_and_receipt_survives_removal(self):
        s=self.app.state; key=next(iter(s.tables['TrialPet']))
        s.inventory['700001']=10000000
        while len(s.pets)<6: s.pets.append(s.preset_pet(1))
        p=s.buy_trial_pet(key)
        self.assertIn(p,s.bank)
        s.bank.remove(p)
        before=s.payload()
        with self.assertRaises(ValueError): s.buy_trial_pet(key)
        self.assertEqual(s.payload(),before)

    def test_legacy_purchase_and_normal_species_not_conflated(self):
        s=self.app.state; key=next(iter(s.tables['TrialPet']))
        p=s.preset_pet(key,'TrialPet');s.receive_pet(p)
        self.assertTrue(s.trial_pet_purchased(key))
        s.save(self.app.save_path)
        loaded=GameState.load(s.tables,self.app.save_path)
        self.assertIn(key,loaded.activities['trial_purchased'])
        s.pets.remove(p)
        p.variation[0]+=1;s.receive_pet(p)
        self.assertFalse(s.trial_pet_purchased(key))

    def test_every_messenger_direct_purchase_is_single_use(self):
        for key in self.app.data.tables['TrialPet']:
            with self.subTest(key=key):
                s=GameState(self.app.data.tables)
                s.inventory['700001']=10000000
                s.buy_trial_pet(key)
                before=s.payload()
                with self.assertRaises(ValueError):s.buy_trial_pet(key)
                self.assertEqual(s.payload(),before)

    def test_six_slots_new_old_and_overflow_bank(self):
        s=self.app.state
        self.assertEqual(s.pet_capacity(),6)
        self.assertEqual(s.count('700004'),6)
        s.grant('700004',10)
        self.assertEqual(s.count('700004'),6)
        s.inventory['700004']=3
        s.save(self.app.save_path)
        s=GameState.load(s.tables,self.app.save_path)
        self.assertEqual(s.pet_capacity(),6)
        self.assertEqual(s.count('700004'),6)
        while len(s.pets)<6:s.receive_pet(s.preset_pet(1))
        p=s.preset_pet(1);s.receive_pet(p)
        self.assertEqual(len(s.pets),6)
        self.assertIn(p,s.bank)
        with self.assertRaises(ValueError):s.move_pet(p.uid,to_bank=False)

    def test_battle_item_and_ball_icons_replace_all_placeholder_resources(self):
        a=self.app
        a.start_battle(next(iter(a.data.tables['VillageEnemy'])),'wild')
        ui=a.battle_ui
        # All real inventory pages, both recovery items and capture balls.
        for key in a.data.tables['PetItem']:
            if key in a.data.tables['Item']:a.state.inventory[key]=2
        for key in ui.battle.catch_items:a.state.inventory[key]=2
        for balls in (False,True):
            rows=ui._battle_items(balls)
            self.assertTrue(rows)
            for page in range((len(rows)+3)//4):
                ui.page=ui.ball_page=page
                with patch.object(ui,'_crop_layout',wraps=ui._crop_layout) as render:
                    ui._draw_item_menu(Image.new('RGBA',(960,576)),balls)
                resources=render.call_args.args[3]
                expected=rows[page*4:(page+1)*4]
                self.assertEqual(len(resources),len(expected))
                for i,(_,row,_) in enumerate(expected,1):
                    path=f'Node/battleItemMenu_Panel/item_Panel/itemMenu_{i}_Button/icon_Image'
                    self.assertEqual(resources[path],'ItemIcon/'+row['texture'])
                    self.assertIsNotNone(a.data.image(resources[path]))

if __name__=='__main__':unittest.main(verbosity=2)
