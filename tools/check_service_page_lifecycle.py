"""Hover must retain live cards; nested service pages cannot finish NPC dialogue."""
import unittest
from types import SimpleNamespace
from PIL import ImageChops,ImageTk
import check_single_window_flows as fixtures

class ServiceChecks(unittest.TestCase):
    setUp=fixtures.SingleWindowChecks.setUp
    tearDown=fixtures.SingleWindowChecks.tearDown
    open=fixtures.SingleWindowChecks.open
    click=fixtures.SingleWindowChecks.click

    def hover_preserves_contents(self):
        a=self.app;page=a.original_page
        self.assertIsNotNone(page)
        base=page.display_frame.copy()
        for key in list(a.ui_buttons):
            rect=a.ui_buttons[key]
            a.on_ui_motion(SimpleNamespace(x=(rect[0]+rect[2])/2,y=(rect[1]+rect[3])/2))
            actual=ImageTk.getimage(a.ui_art_label.composited_image).convert('RGBA')
            expected=a.ui_art_label.backdrop.copy();expected.alpha_composite(page.feedback(a.ui_hover[0] if a.ui_hover else None))
            self.assertIsNone(ImageChops.difference(actual,expected).getbbox(),key)
        a.on_ui_leave()
        self.assertEqual(a.original_page.specs,page.specs)
        self.assertIsNone(ImageChops.difference(page.display_frame,base).getbbox())

    def test_bank_native_cards_remain_visible_and_deposit_withdraw(self):
        a=self.app
        pet=a.state.add_preset(1)
        a.state.move_pet(pet.uid,to_bank=True)
        self.open(4)
        self.assertTrue(any(x[0]=='PetBankItemUI' for x in a.original_page.specs))
        self.assertEqual(a.original_page.specs[0][2]['text']['progress_BitmapFontLabel'],'1/20')
        self.hover_preserves_contents()
        self.click('bank_0/Layer/root_Panel/getBack_Button')
        self.assertIn(pet,a.state.pets)
        self.click('consign_Button')
        self.assertEqual(a.original_page.specs[0][0],'PetSelectUI')
        member=a.state.pets[0]
        self.click('bank_deposit_0')
        self.assertIn(member,a.state.bank)
        self.assertEqual(a.original_page.specs[0][0],'PetBankUI')
        self.hover_preserves_contents()

    def test_skill_native_rows_hover_and_both_lists_scroll(self):
        a=self.app
        while len(a.state.pets)<6:a.state.add_preset(1)
        self.open(6)
        self.assertTrue(any(x[0]=='SkillLearnItemUI' for x in a.original_page.specs))
        self.hover_preserves_contents()
        for _ in range(6):a.page_wheel(SimpleNamespace(delta=-120,x=150))
        self.assertIn('skill_pet_5',a.ui_hits)
        self.click('skill_pet_5')
        self.hover_preserves_contents()
        for _ in range(20):a.page_wheel(SimpleNamespace(delta=-120,x=600))
        self.assertTrue(any(x[0]=='SkillLearnItemUI' for x in a.original_page.specs))

    def enter_service(self,mid,oid):
        a=self.app
        if a.ui_open:a.close_ui()
        a.runtime.file,a.runtime.sequence,a.runtime.pending='',[],None
        a.runtime.queue=[];a.runtime.active_trigger=None
        a.dialogue,a.display_request,a.pending_wait=None,None,None
        a.state.main_task,a.state.main_state=155,5
        a.load_map(mid,544,1120)
        area=next(o for o in a.map.objects if str(o.get('props',{}).get('npcId'))==oid)
        a.x,a.y=float(area['x'])+32,float(area['y'])+32
        a.process_player_areas(force=True)
        self.assertEqual(a.runtime.file,'pEventTalk'+oid+'.json')
        a.interact()
        self.assertTrue(a.ui_open)
        return a

    def test_three_shops_buy_cancel_preserve_openui_until_final_close(self):
        for mid,oid,uiid in [(5802,'580201',1),(5803,'580302',3),(5804,'580401',2)]:
            with self.subTest(npc=oid):
                a=self.enter_service(mid,oid)
                a.state.inventory.update({'700001':10000000,'700002':10000000})
                pending,index=a.runtime.pending,a.runtime.index
                talks=dict(a.state.activities['shop_talks'])
                self.click('shop_goods_0/Layer/root_Panel/buy_Button')
                self.click('cancel_Button')
                self.assertIs(a.runtime.pending,pending);self.assertEqual(a.runtime.index,index)
                self.click('shop_goods_0/Layer/root_Panel/buy_Button')
                self.click('confirm_Button')
                self.assertIs(a.runtime.pending,pending);self.assertEqual(a.runtime.index,index)
                self.assertEqual(int(a.ui_parameters['uiid']),uiid)
                self.assertFalse(a.dialogue)
                self.assertEqual(a.state.activities['shop_talks'],talks)
                self.hover_preserves_contents()
                self.click('close_Button')
                self.assertFalse(a.ui_open)
                self.assertTrue(a.dialogue)
                a.interact()

    def test_skill_confirm_returns_without_advancing_clerk(self):
        a=self.enter_service(5803,'580301')
        pet=a.state.pets[0]
        pet.skills=[];a.state.inventory['700001']=1000000
        pending,index=a.runtime.pending,a.runtime.index
        a._service_skill_page(a.ui_info)
        key=next(k for k in a.ui_actions if k.startswith('skill_row_') and k.endswith('/learn_Button'))
        self.click(key)
        self.assertEqual(a.original_page.specs[0][0],'SkillLearnConfirmUI')
        self.click('close_Button')
        self.assertIs(a.runtime.pending,pending);self.assertEqual(a.runtime.index,index)
        self.assertFalse(a.dialogue)
        self.assertEqual(a.original_page.specs[0][0],'SkillLearnUI')

if __name__=='__main__':unittest.main(verbosity=2)
