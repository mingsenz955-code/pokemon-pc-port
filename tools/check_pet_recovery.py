"""Zero-HP item regression through real tables and both original page entry points."""
import copy
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
import unittest
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'src'))
from game_state import GameState
from original_data import OriginalData
from pc_game import NativeGame
from event_runtime import Request
DATA=OriginalData(ROOT/'original-1.20.4')
HP_ITEMS=('230001','230002','230003','230006','230007')

class PetRecoveryChecks(unittest.TestCase):
    def state(self):
        state=GameState(DATA.tables,seed=19)
        state.initialize(1)
        pet=state.add_preset(1)
        pet.level=30
        return state,pet

    def test_all_ordinary_hp_items_reject_dead_pet_without_spending(self):
        for key in HP_ITEMS:
            with self.subTest(item=key):
                state,pet=self.state();pet.hp=pet.energy=0
                state.inventory[key]=2
                before=copy.deepcopy(state.payload())
                with self.assertRaisesRegex(ValueError,'宠物已死亡，请使用复活石'):
                    state.use_item(key,pet)
                self.assertEqual(before,state.payload())

    def test_partial_hp_and_full_hp_do_not_regress(self):
        state,pet=self.state();state.inventory['230001']=3
        maximum=pet.stats(DATA.tables)[0];pet.hp=maximum-1
        state.use_item('230001',pet)
        self.assertEqual(maximum,pet.hp)
        before=copy.deepcopy(state.payload())
        with self.assertRaises(ValueError):state.use_item('230001',pet)
        self.assertEqual(before,state.payload())

    def test_energy_items_also_reject_dead_pet_without_spending(self):
        for key in ('230004','230005'):
            state,pet=self.state();pet.hp=pet.energy=0;state.inventory[key]=2
            with self.assertRaisesRegex(ValueError,'复活石'):state.use_item(key,pet)
            self.assertEqual((0,0),(pet.hp,pet.energy))
            self.assertEqual(2,state.count(key))

    def test_auto_target_revives_and_save_restore_preserves_result(self):
        state,pet=self.state();pet.hp=0;state.inventory['230008']=2
        state.use_item('230008')
        self.assertGreater(pet.hp,0)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'slot1.json';state.save(path)
            loaded=GameState.load(DATA.tables,path)
            self.assertEqual(pet.hp,loaded.pets[0].hp)
            self.assertEqual(1,loaded.count('230008'))

    def test_empty_inventory_and_foreign_target_cannot_spend_or_heal(self):
        state,pet=self.state();pet.hp=0;state.inventory['230001']=0
        with self.assertRaises(ValueError):state.use_item('230001',pet)
        self.assertEqual(0,pet.hp)
        state.inventory['230001']=2
        with self.assertRaises(ValueError):state.use_item('230001',copy.deepcopy(pet))
        self.assertEqual(0,pet.hp);self.assertEqual(2,state.count('230001'))

    def test_original_revive_item_remains_available(self):
        state,pet=self.state();pet.hp=pet.energy=0;state.inventory['230008']=2
        state.use_item('230008',pet)
        self.assertEqual(max(1,pet.stats(DATA.tables)[0]*30//100),pet.hp)
        self.assertEqual(pet.stats(DATA.tables)[1]*30//100,pet.energy)
        self.assertEqual(1,state.count('230008'))

    def test_real_bag_and_pet_list_show_death_tip_and_allow_revive(self):
        for entry,key in (('bag','230001'),('pets','230001'),('bag','230008'),('pets','230008')):
            with self.subTest(entry=entry),tempfile.TemporaryDirectory() as folder:
                previous=os.environ.get('POCKET_NATIVE_SAVE_DIR')
                os.environ['POCKET_NATIVE_SAVE_DIR']=folder
                root=tk.Tk();root.withdraw();app=None
                try:
                    app=NativeGame(root,DATA)
                    app.runtime.file,app.runtime.sequence,app.runtime.pending='',[],None
                    app.display_request=app.dialogue=app.pending_wait=None
                    app.state,pet=self.state();pet.hp=0
                    app.state.inventory={key:2}
                    if entry=='bag':
                        app.open_ui(Request('openui','test',0,{'parameters':{'uiid':46}}))
                        app.ui_window.withdraw()
                        app.ui_actions['tag_1_Button']()
                        app.ui_actions['use_Button']()
                        self.assertEqual('PetSelectUI',app.original_page.specs[0][0])
                        app.ui_actions['pet_select_0']()
                    else:
                        app.open_ui(Request('openui','test',0,{'parameters':{'uiid':47}}))
                        app.ui_window.withdraw()
                        app.ui_actions['useItem_Button']()
                        app.ui_actions['use_Button']()
                    if key=='230008':
                        self.assertGreater(pet.hp,0)
                        self.assertEqual(1,app.state.count(key))
                        self.assertNotEqual('TipConfirmUI',app.original_page.specs[0][0])
                    else:
                        self.assertEqual(0,pet.hp)
                        self.assertEqual(2,app.state.count(key))
                        self.assertIn('复活石',app.ui_info.get())
                        self.assertEqual('TipConfirmUI',app.original_page.specs[-1][0])
                finally:
                    if app and app.ui_window and app.ui_window.winfo_exists():app.ui_window.destroy()
                    for job in root.tk.call('after','info'):root.after_cancel(job)
                    root.destroy()
                    if previous is None:os.environ.pop('POCKET_NATIVE_SAVE_DIR',None)
                    else:os.environ['POCKET_NATIVE_SAVE_DIR']=previous

if __name__=='__main__':unittest.main(verbosity=2)
