"""Native battle shop cards, real pointer clicks, turn suspension and purchase rollback."""
import copy
from types import SimpleNamespace
from unittest.mock import patch
import unittest
import time
import check_single_window_flows as fixtures
from event_runtime import Request
from game_overlay import GameOverlay

class BattleShopChecks(unittest.TestCase):
    setUp=fixtures.SingleWindowChecks.setUp
    tearDown=fixtures.SingleWindowChecks.tearDown
    click=fixtures.SingleWindowChecks.click
    def open_shop(self):
        a=self.app
        a.start_battle(next(iter(a.data.tables['VillageEnemy'])),'wild')
        a.battle_ui.render()
        rect=a.battle_ui.hits['battleShop_Button']
        a.on_click(SimpleNamespace(x=(rect[0]+rect[2])/2,y=(rect[1]+rect[3])/2))
        self.assertTrue(a.ui_open)
        self.assertIsInstance(a.ui_window,GameOverlay)
        self.assertEqual('BattleShopUI',a.original_page.specs[0][0])
        return a
    def buy_card(self,index=0):
        key=next(k for k in self.app.ui_actions if k.startswith(f'shop_goods_{index}/') and k.endswith('/buy_Button'))
        self.click(key)
        self.assertEqual('BuyConfirmUI',self.app.original_page.specs[0][0])

    def test_original_card_buttons_and_close_are_inside_visible_game(self):
        a=self.open_shop()
        self.assertTrue(any(s[0]=='ShopGoodsUI' for s in a.original_page.specs))
        self.assertFalse(any(c.winfo_class() in ('Toplevel','Listbox') for c in a.root.winfo_children()))
        for key in ('close_Button',next(k for k in a.ui_actions if k.startswith('shop_goods_0/') and k.endswith('/buy_Button'))):
            rect=next(v for k,v in a.ui_hits.items() if k==key or k.endswith('/'+key))
            self.assertTrue(0<=rect[0]<rect[2]<=800 and 0<=rect[1]<rect[3]<=480)
        a.ui_base_layer.save(fixtures.fixtures.OUT/'battle-shop-0.2.66.png')
        self.click('close_Button')
        self.assertFalse(a.ui_open)
        self.assertIsNotNone(a.battle)

    def test_buy_quantity_costs_once_and_returns_to_same_battle(self):
        a=self.open_shop();battle=a.battle
        key='201';row=a.data.tables['BattleShop'][key]
        before_gold=a.state.count(row['moneyType']);before_items=a.state.count(row['goodsKid']);round_no=battle.round
        self.buy_card();self.click('right_Button');self.click('confirm_Button')
        self.assertEqual('BattleShopUI',a.original_page.specs[0][0])
        self.assertIs(battle,a.battle)
        self.assertEqual(round_no,battle.round)
        self.assertEqual(before_gold-2*int(row['price']),a.state.count(row['moneyType']))
        self.assertEqual(before_items+2,a.state.count(row['goodsKid']))
        self.click('close_Button');a.battle_ui.item_filter=None
        self.assertIn(row['goodsKid'],[r[0] for r in a.battle_ui._battle_items(True)])

    def test_cancel_and_insufficient_funds_preserve_inventory(self):
        a=self.open_shop();before=copy.deepcopy(a.state.inventory)
        self.buy_card();self.click('cancel_Button')
        self.assertEqual(before,a.state.inventory)
        a.state.inventory['700001']=0;before=copy.deepcopy(a.state.inventory)
        self.buy_card();self.click('confirm_Button')
        self.assertIn('不足',a.ui_info.get())
        self.assertEqual(before,a.state.inventory)
        self.click('confirm_Button')
        self.assertEqual('BuyConfirmUI',a.original_page.specs[0][0])
        self.click('cancel_Button');self.click('close_Button')
        self.assertFalse(a.ui_open)

    def test_scroll_reaches_all_twelve_cards_and_last_purchase(self):
        a=self.open_shop()
        a.shop_scroll(100)
        self.assertTrue(any(k.startswith('shop_goods_11/') and k.endswith('/buy_Button') for k in a.ui_actions))
        row=a.data.tables['BattleShop']['212'];before=a.state.count(row['goodsKid'])
        self.buy_card(11);self.click('confirm_Button')
        self.assertEqual(before+1,a.state.count(row['goodsKid']))
        self.assertEqual(11,a.battle_shop_view[0])
        self.assertTrue(any(k.startswith('shop_goods_11/') and k.endswith('/buy_Button') for k in a.ui_actions))

    def test_shop_tick_does_not_render_or_advance_battle(self):
        a=self.open_shop();battle=a.battle
        before=(battle.round,[(u.hp,u.energy) for u in battle.player+battle.enemy])
        with patch.object(a.battle_ui,'advance') as advance,patch.object(a.battle_ui,'render') as render:
            a._play_clock=time.monotonic()-.5
            a.tick()
            advance.assert_not_called();render.assert_not_called()
        self.assertEqual(before,(battle.round,[(u.hp,u.energy) for u in battle.player+battle.enemy]))
        with patch.object(a.battle_ui,'click') as click:
            a.on_click(SimpleNamespace(x=10,y=10));click.assert_not_called()

    def test_close_and_confirmation_never_resume_pending_story_fight(self):
        a=self.open_shop();pending=Request('fight','test',0,{'parameters':{}})
        a.runtime.pending=pending
        self.buy_card();self.click('cancel_Button');self.click('close_Button')
        self.assertIs(pending,a.runtime.pending)

    def test_fullscreen_purchase_click_coordinates(self):
        a=self.open_shop()
        self.root.attributes('-alpha',0)
        self.root.deiconify()
        self.root.geometry('1536x864')
        self.root.update()
        a.ui_window.deiconify()
        self.root.update()
        rect=next(v for k,v in a.ui_hits.items() if k.startswith('shop_goods_0/') and k.endswith('/buy_Button'))
        scale=a.viewport.scale
        x,y=round((rect[0]+rect[2])/2*scale),round((rect[1]+rect[3])/2*scale)
        a.ui_art_label.event_generate('<ButtonPress-1>',x=x,y=y)
        a.ui_art_label.event_generate('<ButtonRelease-1>',x=x,y=y)
        self.root.update()
        self.assertEqual('BuyConfirmUI',a.original_page.specs[0][0])
        self.click('cancel_Button');self.click('close_Button')
        self.assertFalse(a.ui_open)

    def test_purchased_healing_item_can_be_used_after_return(self):
        a=self.open_shop()
        self.buy_card(2);self.click('confirm_Button');self.click('close_Button')
        unit=a.battle.player_active;unit.hp=1
        before=a.state.count('230001')
        ui=a.battle_ui
        ui.selected={'id':'230001','kind':'item'}
        with patch.object(a.battle,'_enemy_action',return_value={'type':'skip'}):
            ui._action('confirm_yes')
        self.assertGreater(unit.hp,1)
        self.assertEqual(before-1,a.state.count('230001'))
        self.assertTrue(any(e['type']=='item_used' for e in a.battle.events))

if __name__=='__main__':unittest.main(verbosity=2)
