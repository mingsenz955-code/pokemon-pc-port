import unittest
import check_single_window_flows as fixtures
from game_state import numbers,GameState

class SkillLearningChecks(unittest.TestCase):
 setUp=fixtures.SingleWindowChecks.setUp
 tearDown=fixtures.SingleWindowChecks.tearDown
 click=fixtures.SingleWindowChecks.click
 open=fixtures.SingleWindowChecks.open
 def paid(self):
  a=self.app
  species=next(k for k,r in a.data.tables['Pet'].items() if len(numbers(r['skillIds']))>4)
  p=a.state.add_generated_pet(species);a.state.pets=[p]
  skills=[str(x) for x in numbers(a.data.tables['Pet'][species]['skillIds'])]
  p.skills=skills[:4];return p,skills[4]
 def test_npc_full_slots_select_replace_pay_once_and_save(self):
  a=self.app;p,key=self.paid();row=a.data.tables['Skill'][key];a.state.inventory[row['moneyId']]=1000000
  before=a.state.count(row['moneyId']);old=p.skills[1]
  a.open_skill_learn_confirm(p.uid,key,back=6)
  self.assertEqual(a.original_page.specs[0][0],'SkillReplaceUI')
  self.click('replace_slot_1');self.click('confirm_Button')
  self.assertEqual(p.skills[1],key);self.assertNotIn(old,p.skills)
  self.assertEqual(a.state.count(row['moneyId']),before-int(row['moneyCount']))
  self.click('confirm_Button');self.assertEqual(a.original_page.specs[0][0],'SkillLearnUI')
  self.assertIn(key,GameState.load(a.data.tables,a.save_path).pets[0].skills)
 def test_scroll_full_slots_cancel_then_replace_consumes_once(self):
  a=self.app;p,_=self.paid()
  item,row=next((k,r) for k,r in a.data.tables['SkillItem'].items() if r['skillId'] in a.data.tables['Skill'] and r['skillId'] not in p.skills)
  key=row['skillId'];a.state.grant(item,2);gold=a.state.count('700001')
  a.open_skill_learn_confirm(p.uid,key,scroll=item,back=46);self.click('close_Button')
  self.assertEqual(a.state.count(item),2)
  a.open_skill_learn_confirm(p.uid,key,scroll=item,back=46);self.click('replace_slot_2');self.click('confirm_Button')
  self.assertEqual(p.skills[2],key);self.assertEqual(a.state.count(item),1);self.assertEqual(a.state.count('700001'),gold)
 def test_insufficient_npc_funds_shows_visible_tip_without_mutation(self):
  a=self.app;p,key=self.paid();money=a.data.tables['Skill'][key]['moneyId'];a.state.inventory[money]=0
  a.open_skill_learn_confirm(p.uid,key,back=6);before=a.state.payload();self.click('confirm_Button')
  self.assertEqual(a.original_page.specs[0][0],'TipConfirmUI');self.assertEqual(a.state.payload(),before)
 def test_medal_pack_is_one_million_for_ten(self):
  s=self.app.state;row=s.tables['Store']['105'];self.assertEqual(row['gotCount'],'10');self.assertEqual(row['costCount'],'1000000')
  s.inventory['700001']=1000000;s.inventory['700002']=0;s.buy_store('105')
  self.assertEqual(s.count('700002'),10);self.assertEqual(s.count('700001'),0)

if __name__=='__main__':unittest.main(verbosity=2)
