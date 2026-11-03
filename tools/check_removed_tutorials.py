"""Removed online/location lessons cannot block new or restored PC saves."""
import unittest,copy,json
import check_single_window_flows as fixtures
from event_runtime import EventRuntime,Request
from offline_tutorials import removed_tutorial_step,REMOVED_SCENE_BUTTONS

class RemovedTutorialChecks(unittest.TestCase):
    setUp=fixtures.SingleWindowChecks.setUp
    tearDown=fixtures.SingleWindowChecks.tearDown

    def test_rank_tail_finishes_without_dialogue_unlock_or_sound(self):
        a=self.app;r=a.runtime;r.start('pEvent5901002.json');r.jump(18)
        before=copy.deepcopy(a.state.functions);sounds=[];r.play_sound=sounds.append
        a.drive()
        self.assertFalse(r.running);self.assertIsNone(a.display_request)
        self.assertEqual(a.state.functions,before);self.assertEqual(sounds,[])
        self.assertIsNone(a.state.pending_runtime)

    def test_old_saved_rank_button_and_menu_wait_are_removed(self):
        for identifier in (19,20,21):
            a=self.app;r=EventRuntime(a.data,a.state);r.start('pEvent5901002.json');r.jump(identifier)
            step=r.sequence[r.index]
            r.pending=Request(step['type'],r.file,identifier,copy.deepcopy(step));r.persist()
            saved=r.snapshot();restored=EventRuntime(a.data,a.state);restored.restore(saved)
            self.assertIsNone(restored.next());self.assertFalse(restored.running)

    def test_shop_location_tail_removed_but_main_task_and_story_kept(self):
        a=self.app;r=a.runtime;r.start('pEvent101003.json')
        req=r.next();self.assertEqual(req.kind,'talk');self.assertIn('商店',req.data['text'])
        r.pending=None;r.jump(6);self.assertIsNone(r.next());self.assertFalse(r.running)
        # Quest commands preceding the removed tail have not been deleted.
        self.assertTrue(any(s['type']=='submittask' for s in a.data.event('pEvent101003.json')))

    def test_no_hidden_button_tutorial_remains_and_hatch_guides_survive(self):
        d=self.app.data
        for path in (d.root/'events').glob('*.json'):
            sequence=json.loads(path.read_text('utf8'))
            if not isinstance(sequence,list):continue
            for step in sequence:
                if step.get('nodekey') in REMOVED_SCENE_BUTTONS:
                    self.assertTrue(removed_tutorial_step(path.name,step))
        normal=[s for s in d.event('pEvent5905001.json') if s['type']=='button']
        self.assertTrue(normal)
        self.assertFalse(any(removed_tutorial_step('pEvent5905001.json',s) for s in normal))

if __name__=='__main__':unittest.main(verbosity=2)
