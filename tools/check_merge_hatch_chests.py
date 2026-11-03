import unittest,copy
from types import SimpleNamespace
import check_single_window_flows as fixtures
from activities import Activities
from game_state import numbers,GameState
from guide import GuideTarget

class MergeHatchChestChecks(unittest.TestCase):
    setUp=fixtures.SingleWindowChecks.setUp
    tearDown=fixtures.SingleWindowChecks.tearDown
    open=fixtures.SingleWindowChecks.open
    click=fixtures.SingleWindowChecks.click

    def setup_merge(self,bad=False):
        a=self.app;a.state.bank=[];a.state.inventory['700002']=20
        pets=[]
        for level in (10,9 if bad else 10):
            p=a.state.add_generated_pet('100028',level);p.quality=1
            if p in a.state.pets:a.state.pets.remove(p)
            if p not in a.state.bank:a.state.bank.append(p)
            pets.append(p)
        self.open(18)
        self.assertEqual(a.original_page.specs[0][0],'MergePetUI')
        self.click('merge_base');self.click('merge_pick_0')
        self.click('merge_mat_0');self.click('merge_pick_0')
        self.assertIsNone(a.page_wheel)
        return pets

    def test_merge_real_cards_deduct_once_and_save_result(self):
        a=self.app;base,material=self.setup_merge()
        before=list(base.growth);balance=a.state.count('700002')
        self.click('merge_Button')
        self.assertEqual(a.original_page.specs[0][0],'TipConfirmUI')
        self.assertIn('融合成功',a.ui_info.get())
        self.assertEqual(base.growth,[x+.5 for x in before])
        self.assertIn(base,a.state.bank);self.assertNotIn(material,a.state.bank)
        self.assertEqual(a.state.count('700002'),balance-2)
        loaded=GameState.load(a.data.tables,a.save_path)
        self.assertEqual(loaded.bank[0].growth,base.growth)
        self.click('confirm_Button')
        self.assertEqual(a.original_page.specs[0][0],'MergePetUI')
        self.assertIsNone(a.page_wheel)

    def test_invalid_merge_displays_error_without_consuming(self):
        a=self.app;self.setup_merge(bad=True);before=a.state.payload()
        self.click('merge_Button')
        self.assertEqual(a.original_page.specs[0][0],'TipConfirmUI')
        self.assertEqual(a.state.payload(),before)

    def test_material_hatching_requires_experience_and_materials(self):
        s=self.app.state;act=Activities(s);s.grant('250006',1);act.put_egg(0,'250006')
        row=s.tables['HatchItem']['250006']
        for k in numbers(row['itemIds']):s.inventory[str(k)]=0
        before=s.payload()
        with self.assertRaises(ValueError):act.hatch(0)
        self.assertEqual(s.payload(),before)
        act.add_hatch_exp(int(row['exp']))
        before=s.payload()
        with self.assertRaises(ValueError):act.hatch(0)
        self.assertEqual(s.payload(),before)
        for k,n in zip(numbers(row['itemIds']),numbers(row['itemCounts'])):s.grant(k,n)
        act.hatch(0)
        for k in numbers(row['itemIds']):self.assertEqual(s.count(k),0)
        self.assertIsNotNone(s.activities['eggs']['0']['pet'])

    def test_original_money_hatching_spends_gold_without_materials(self):
        s=self.app.state;act=Activities(s);s.grant('250006',1);act.put_egg(0,'250006')
        row=s.tables['HatchItem']['250006']
        for k in numbers(row['itemIds']):s.inventory[str(k)]=0
        s.inventory[row['moneyId']]=int(row['moneyCount'])
        act.hatch(0,use_money=True)
        self.assertEqual(s.count(row['moneyId']),0)
        self.assertEqual(s.activities['eggs']['0']['exp'],0)
        for k in numbers(row['itemIds']):self.assertEqual(s.count(k),0)

    def test_shop_chest_reused_npc_id_targets_chest_not_counter(self):
        a=self.app;a.state.main_task,a.state.main_state=155,5
        a.load_map(5802,544,960)
        chest=next(t for t in a.actors() if t[1]=='30001')
        oid,sid,x,y=chest
        self.assertTrue(any(str(o.get('props',{}).get('npcId'))==oid for o in a.map.objects))
        for dx,dy in [(64,0),(-64,0),(0,64),(0,-64)]:
            px,py=x+dx,y+dy
            if not a.map.blocked(px,py):a.x,a.y=px,py;break
        a.guide.start_click(x,y,oid,sid)
        for _ in range(1000):
            if not a.guide.active:break
            a.guide.step(.04)
        self.assertIn(oid,a.state.activities.get('village_chests',[]))
        self.assertTrue(a.ui_open)
        self.click('confirm_Button')
        before=a.state.payload()
        a.interact(oid,sid)
        self.assertEqual(a.state.payload(),before)
        self.assertIn('打开',a.scene_ui.tip[0])

    def test_every_map_chest_has_original_reward_row(self):
        d=self.app.data;missing=[];count=0
        for mid in d.tables['VillageMap']:
            world=d.load_map(mid)
            for obj in world.objects:
                if obj.get('gid') and world.tile_properties(int(obj['gid'])).get('spriteId')=='30001':
                    count+=1
                    if str(obj.get('name')) not in d.tables['VillageChest']:missing.append((mid,obj.get('name')))
        self.assertGreater(count,300)
        self.assertEqual(missing,[])

if __name__=='__main__':unittest.main(verbosity=2)
