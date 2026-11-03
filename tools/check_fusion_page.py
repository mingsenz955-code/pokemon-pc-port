"""Real native fusion slot selection, confirmation, costs and rollback."""
import unittest
from pathlib import Path
import check_single_window_flows as fixtures
from game_state import numbers, GameState

class FusionChecks(unittest.TestCase):
    setUp=fixtures.SingleWindowChecks.setUp
    tearDown=fixtures.SingleWindowChecks.tearDown
    open=fixtures.SingleWindowChecks.open
    click=fixtures.SingleWindowChecks.click

    def parents(self):
        a=self.app;s=a.state
        row=next(iter(s.tables['PetHeTi'].values()))
        s.bank=[]
        for species in [row['petAId'],row['petBId']]:
            pet=s.add_generated_pet(species,30)
            if pet in s.pets:s.pets.remove(pet)
            if pet not in s.bank:s.bank.append(pet)
        for kid,amount in zip(numbers(row['costItemIds']),numbers(row['costItemCounts'])):
            s.inventory[str(kid)]=amount
        return row,list(s.bank)

    def choose(self):
        self.open(34)
        self.click('add_1_Button')
        self.assertEqual(self.app.original_page.specs[0][0],'PetSelectUI')
        self.click('fuse_pick_0')
        self.click('add_2_Button')
        self.click('fuse_pick_0')

    def test_real_buttons_select_confirm_and_complete_once(self):
        a=self.app;row,parents=self.parents()
        self.choose()
        specs=a.original_page.specs
        self.assertTrue(any(s[0]=='ConditionItemUI' for s in specs))
        self.assertTrue(a.original_page.animated_pets)
        before=a.state.payload()
        self.click('heTi_Button')
        self.assertEqual(a.original_page.specs[0][0],'SecondConfirmUI')
        self.assertEqual(before,a.state.payload())
        self.click('confirm_Button')
        self.assertEqual(len(a.state.bank),1)
        child=a.state.bank[0]
        self.assertEqual(child.level,1)
        self.assertIn(child.species,row['petIds'].split(','))
        self.assertFalse(any(p.uid in [x.uid for x in parents] for p in a.state.pets+a.state.bank))
        loaded=GameState.load(a.data.tables,a.save_path)
        self.assertEqual(loaded.bank[0].uid,child.uid)
        self.assertEqual(a.original_page.specs[0][0],'GetItemUI')

    def test_cancel_does_not_consume_and_empty_bank_is_actionable(self):
        a=self.app;self.parents();self.choose()
        before=a.state.payload();self.click('heTi_Button');self.click('cancel_Button')
        self.assertEqual(a.state.payload(),before)
        self.assertEqual(a.original_page.specs[0][0],'PetHeTiUI')
        a.state.bank=[];self.open(34)
        visible=a.original_page.specs[0][2]['visible']
        self.assertFalse(visible['Layer/root_Panel/add_1_Button/info_Panel'])
        self.click('add_1_Button')
        self.assertEqual(a.original_page.specs[0][0],'TipConfirmUI')

    def test_missing_material_keeps_parents_and_money(self):
        a=self.app;row,_=self.parents();self.choose()
        a.state.inventory[str(numbers(row['costItemIds'])[0])]=0
        before=a.state.payload();self.click('heTi_Button');self.click('confirm_Button')
        self.assertEqual(a.state.payload(),before)
        self.assertEqual(a.original_page.specs[0][0],'TipConfirmUI')

if __name__=='__main__':unittest.main(verbosity=2)
