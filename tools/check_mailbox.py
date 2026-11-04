import json,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import check_single_window_flows as fixtures
from mailbox_system import Mailbox
from game_state import GameState

class MailChecks(unittest.TestCase):
 setUp=fixtures.SingleWindowChecks.setUp
 tearDown=fixtures.SingleWindowChecks.tearDown
 click=fixtures.SingleWindowChecks.click
 def feed(self,to='all'):
  return {'format':1,'messages':[{'id':'test-1','title':'测试邮件','body':'测试正文','to':to,'rewards':[{'item':'700001','count':100},{'item':'220001','count':2}]}]}
 def test_claim_once_persists_and_target_filters(self):
  a=self.app;b=Mailbox(a.state);b.merge(self.feed(['someone-else']));self.assertFalse(b.messages())
  b.data['messages']=[];b.merge(self.feed([b.data['player_id']]));before=a.state.count('700001');b.claim('test-1')
  self.assertEqual(a.state.count('700001'),before+100)
  with self.assertRaises(ValueError):b.claim('test-1')
  b.merge({'format':1,'messages':[]});self.assertEqual(len(b.messages()),1)
  a.save();loaded=GameState.load(a.data.tables,a.save_path)
  with self.assertRaises(ValueError):Mailbox(loaded).claim('test-1')
 def test_expiry_invalid_feed_and_transaction_failure_do_not_grant(self):
  a=self.app;b=Mailbox(a.state);feed=self.feed();feed['messages'][0]['expires_at']='2000-01-01T00:00:00Z';b.merge(feed)
  before=a.state.payload()
  with self.assertRaises(ValueError):b.claim('test-1')
  self.assertEqual(a.state.payload(),before)
  bad=self.feed();bad['messages'][0]['rewards'][0]['count']=-1
  with self.assertRaises(ValueError):b.merge(bad)
  b.data['messages']=[];b.merge(self.feed());before=a.state.payload()
  with patch.object(a.state,'grant_many',side_effect=ValueError('failed')):
   with self.assertRaises(ValueError):b.claim('test-1')
  self.assertEqual(a.state.payload(),before)
 def test_real_mail_page_click_read_claim_return(self):
  a=self.app;b=Mailbox(a.state);b.merge(self.feed())
  with patch('mail_pages.download',return_value=self.feed()):
   a.mailbox_ui();self.click('mail_row_0');self.assertIn('test-1',b.data['read'])
   self.click('mail_claim');self.assertIn('test-1',b.data['claimed'])
   self.assertEqual(a.original_page.specs[0][0],'GetItemUI');self.click('confirm_Button')
   self.click('mail_claim');self.assertEqual(b.data['claimed'].count('test-1'),1)
   a.ui_base_layer.save('outputs/verification/mailbox.png')
 def test_balance_mail_confirms_before_lowering_and_only_grants_once(self):
  a=self.app;s=a.state;b=Mailbox(s)
  feed=json.loads((Path(__file__).resolve().parents[1]/'distribution/mailbox.json').read_text('utf8'))
  kid=feed['messages'][0]['id'];b.merge(feed)
  s.inventory.update({'700001':125000,'700002':7})
  with patch('mail_pages.download',return_value=feed):
   a.mailbox_ui();self.click('mail_row_0');self.click('mail_claim')
   self.assertEqual(a.original_page.specs[0][0],'SecondConfirmUI')
   self.click('cancel_Button')
   self.assertEqual(s.count('700001'),125000)
   self.assertEqual(s.count('700002'),7)
   self.click('mail_claim');self.click('confirm_Button')
   self.assertEqual(s.count('700001'),20000)
   self.assertEqual(s.count('700002'),17)
   self.click('confirm_Button');self.click('mail_claim')
   self.assertEqual(s.count('700002'),17)
   self.assertIn(kid,Mailbox(GameState.load(a.data.tables,a.save_path)).data['claimed'])
 def test_nurse_is_free_revives_and_keeps_all_currency(self):
  a=self.app;s=a.state;pet=s.pets[0];pet.hp=0;pet.energy=0
  before=dict(s.inventory);self.assertEqual(s.cure_cost(),(None,0));s.cure_party()
  self.assertEqual(s.inventory,before);self.assertGreater(pet.hp,0);self.assertGreater(pet.energy,0)
 def test_gold_80000_bundle_once_across_aliases_and_legacy_saves(self):
  a=self.app;s=a.state;s.inventory['700001']=20000
  s.buy_store('202');self.assertEqual(s.count('700001'),80000)
  before=s.payload()
  for key in ('202','2202'):
   with self.assertRaises(ValueError):s.buy_store(key)
   self.assertEqual(s.payload(),before)
  a.save();loaded=GameState.load(a.data.tables,a.save_path)
  with self.assertRaises(ValueError):loaded.buy_store('202')
  loaded.shop_purchases={'Store:2202':1}
  self.assertTrue(loaded.store_bought_out('202'))
  with self.assertRaises(ValueError):loaded.buy_store('202')

 def test_hud_mail_is_left_of_task_and_clickable(self):
  from PIL import Image
  a=self.app;a.scene_ui.render(Image.new('RGBA',(960,576)))
  mail=a.scene_ui.hits['mailbox_Button'];task=a.scene_ui.hits['task_Button']
  self.assertLessEqual(mail[2],task[0])
  self.assertAlmostEqual(mail[2]-mail[0],task[2]-task[0],delta=0.5)
  self.assertAlmostEqual(mail[3]-mail[1],task[3]-task[1],delta=0.5)
  with patch.object(a,'mailbox_ui') as opened:a.scene_ui.action('mailbox_Button');opened.assert_called_once()

if __name__=='__main__':unittest.main(verbosity=2)
