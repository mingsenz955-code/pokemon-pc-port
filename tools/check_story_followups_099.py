"""Story task conditions and the real two-pet handover chain, isolated saves."""
import copy
import json
import os
import sys
import tempfile
import shutil
import hashlib
import unittest
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from game_state import GameState
from task_progress import TaskProgress
from task_costs import TaskCosts
from event_runtime import EventRuntime
from guide import GuideResolver
from task_page import TaskPage
from story_handover_recovery import recover_legacy_handover

DATA = OriginalData(ROOT/'x-data')
OUT = ROOT/'outputs/verification/0.2.99'
OUT.mkdir(parents=True, exist_ok=True)


def state():
    result = GameState(DATA.tables, 99)
    result.initialize(1)
    result.add_preset(next(iter(DATA.tables['InitPet'])))
    result.main_task, result.main_state = 197, 3
    return result


class StoryFollowups(unittest.TestCase):
    def test_committed_handover_request_resumes_without_empty_pet_selector(self):
        from task_handover import TaskHandover
        s=state()
        cost=TaskCosts(s, {'mtask':197})
        cost.mark_committed()
        resumed=[]
        app=SimpleNamespace(state=s,runtime=SimpleNamespace(resume=resumed.append))
        request=SimpleNamespace(data={'parameters':{'mtask':197}})
        self.assertTrue(TaskHandover.begin_task_handover(app,request))
        self.assertEqual([[]],resumed)

    def test_task_header_counts_submitted_tasks_not_current_task_number(self):
        s=state()
        s.main_task,s.main_state=131,3
        s.completed_main=list(range(1,131))
        page=TaskPage(SimpleNamespace(state=s,data=DATA))
        observed=[]
        render=page.ui.render
        def observe(name,*args,**kwargs):
            if name=='TaskUI': observed.append(args[1]['progress_BitmapFontLabel'])
            return render(name,*args,**kwargs)
        page.ui.render=observe
        page.render()
        self.assertEqual(['130/260'],observed)

    def test_131_handover_stays_ready_until_original_cave_arrival_submits(self):
        s=state()
        s.main_task,s.main_state=131,3
        s.events['503004']=1
        uids=[s.add_generated_pet('100093',20).uid for _ in range(5)]
        TaskProgress(s).update()
        runtime=EventRuntime(DATA,s)
        self.assertTrue(runtime.notify('talk',npcid=50314))
        played=[]
        for _ in range(100):
            request=runtime.next()
            if request is None: break
            played.append(request.event)
            if request.kind=='costtaskitem':
                runtime.resume(uids)
                TaskProgress(s).update()
                self.assertEqual((4,[5]),(s.main_state,s.task_counts['main:131']))
                self.assertFalse([p for p in s.pets+s.bank if p.species=='100093'])
            else:
                if request.kind=='tomap':
                    self.assertEqual(60301,request.data['parameters']['exit'])
                    s.map_id=603
                    runtime.notify('tomap',map=603)
                runtime.resume()
            TaskProgress(s).update()
        self.assertEqual(132,s.main_task)
        self.assertIn(131,s.completed_main)
        self.assertIn('pEvent603001.json',played)
        self.assertEqual(1,s.events['603001'])

    def test_receipt_is_atomic_and_resume_never_charges_twice(self):
        s=state()
        s.main_task,s.main_state=131,3
        uids=[s.add_generated_pet('100093',20).uid for _ in range(5)]
        cost=TaskCosts(s,{'mtask':131})
        with self.assertRaises(ValueError): cost.consume(uids[:4])
        self.assertFalse(cost.committed())
        self.assertEqual(5,len(cost.candidates('100093')))
        cost.consume(uids)
        after=[p.uid for p in s.pets+s.bank]
        cost.consume(uids)
        self.assertTrue(cost.committed())
        self.assertEqual(after,[p.uid for p in s.pets+s.bank])

    def test_collection_can_still_become_unready_before_actual_handover(self):
        s=state()
        s.main_task,s.main_state=131,3
        pets=[s.add_generated_pet('100093',20) for _ in range(5)]
        TaskProgress(s).update()
        self.assertEqual(4,s.main_state)
        s.pets.remove(pets[0])
        TaskProgress(s).update()
        self.assertEqual(3,s.main_state)

    def test_legacy_131_requires_committed_event_proof(self):
        s=state()
        s.main_task,s.main_state=131,3
        s.map_id=503
        s.events['503004']=1
        self.assertIsNone(recover_legacy_handover(DATA,s))
        s.events['503005']=1
        plan=recover_legacy_handover(DATA,s)
        self.assertEqual({'event':'pEvent503005.json','index':7,'arrival_map':603},plan)
        TaskProgress(s).update()
        self.assertEqual((4,[5]),(s.main_state,s.task_counts['main:131']))
        self.assertIsNone(recover_legacy_handover(DATA,s))

    def test_actual_stuck_save_copy_resumes_to_132_and_is_backed_up(self):
        import time
        import tkinter as tk
        from pc_game import NativeGame
        source=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'PocketNativePC/slot1.json'
        if not source.is_file(): self.skipTest('Player save is not present')
        raw=source.read_bytes()
        snapshot=json.loads(raw)
        if (snapshot['state'].get('main_task')!=131 or snapshot['state'].get('events',{}).get('503005')!=1):
            self.skipTest('The live save has progressed beyond the reported issue')
        previous=os.environ.get('POCKET_NATIVE_SAVE_DIR')
        with tempfile.TemporaryDirectory(prefix='pocket-story-131-copy-') as folder:
            os.environ['POCKET_NATIVE_SAVE_DIR']=folder
            path=Path(folder)/'slot1.json'
            path.write_bytes(raw)
            root=tk.Tk()
            root.withdraw()
            try:
                app=NativeGame(root,DATA)
                app.audio.set_enabled('music',False)
                app.audio.set_enabled('effect',False)
                for _ in range(500):
                    root.update()
                    if app.state.main_task==132 and not app.runtime.running: break
                    if getattr(app,'reward_visible',False):
                        app.ui_actions['confirm_Button']()
                    app.drive()
                    time.sleep(.005)
                self.assertEqual('',app.runtime_error)
                self.assertEqual(132,app.state.main_task)
                self.assertFalse(app.runtime.running)
                self.assertIn(131,app.state.completed_main)
                self.assertEqual(1,app.state.events['603001'])
                backup=path.with_name('slot1.before-story-0.2.99.json')
                self.assertEqual(hashlib.sha256(raw).hexdigest(),hashlib.sha256(backup.read_bytes()).hexdigest())
                app.save()
                restored=GameState.load(DATA.tables,path)
                self.assertEqual(132,restored.main_task)
                self.assertEqual(1,restored.events['603001'])
            finally:
                if 'app' in locals(): app.close_transient_ui()
                for job in root.tk.call('after','info'): root.after_cancel(job)
                root.destroy()
                if previous is None: os.environ.pop('POCKET_NATIVE_SAVE_DIR',None)
                else: os.environ['POCKET_NATIVE_SAVE_DIR']=previous

    def test_all_260_main_and_232_branch_condition_updates(self):
        errors = []
        for table, branch in [('MainTask',False),('BranchTask',True)]:
            for key in DATA.tables[table]:
                s = state()
                s.main_task, s.main_state = (1,5) if branch else (int(key),3)
                s.branch_states = {key:3} if branch else {}
                try:
                    TaskProgress(s).update()
                except Exception as error:
                    errors.append((table,key,str(error)))
        self.assertEqual([],errors)

    def test_task_196_reward_and_transition_do_not_roll_back(self):
        s = state()
        s.main_task, s.main_state = 196,4
        self.assertTrue(s.submit_task(196))
        self.assertEqual((197,3),(s.main_task,s.main_state))
        self.assertIn(196,s.completed_main)

    def test_two_distinct_species_are_required_and_bank_counts(self):
        s = state()
        TaskProgress(s).update()
        self.assertEqual([0,0],s.task_counts['main:197'])
        first = s.add_generated_pet('100171',12)
        s.add_generated_pet('100171',12)
        TaskProgress(s).update()
        self.assertEqual(3,s.main_state)
        self.assertEqual([2,0],s.task_counts['main:197'])
        second = s.add_generated_pet('100172',12)
        s.move_pet(second.uid,to_bank=True)
        TaskProgress(s).update()
        self.assertEqual(4,s.main_state)
        s.bank.remove(second)
        TaskProgress(s).update()
        self.assertEqual(3,s.main_state)

    def test_existing_one_slot_counter_is_recomputed_without_fake_credit(self):
        s = state()
        s.task_counts['main:197']=[999]
        TaskProgress(s).update()
        self.assertEqual([0,0],s.task_counts['main:197'])
        self.assertEqual(3,s.main_state)

    def test_original_1607002_handover_consumes_selected_uids_once(self):
        s = state()
        first = s.add_generated_pet('100171',12)
        spare = s.add_generated_pet('100171',15)
        second = s.add_generated_pet('100172',12)
        TaskProgress(s).update()
        s.events['1607001']=1
        runtime = EventRuntime(DATA,s)
        self.assertTrue(runtime.notify('talk',npcid=160701))
        self.assertEqual('pEvent1607002.json',runtime.file)
        count = 0
        while runtime.running and count < 100:
            count += 1
            request=runtime.next()
            if request is None: break
            if request.kind == 'costtaskitem':
                runtime.resume([first.uid,second.uid])
            elif request.kind in ('fight','battleover'):
                self.fail('This handover is not a battle')
            else:
                runtime.resume()
        self.assertFalse(runtime.running)
        self.assertEqual(198,s.main_task)
        self.assertEqual(1,s.events['1607002'])
        self.assertIn(197,s.completed_main)
        self.assertIn(spare,s.pets)
        self.assertNotIn(first,s.pets)
        self.assertNotIn(second,s.pets)
        with self.assertRaises(ValueError):
            TaskCosts(s,{'mtask':197}).consume([first.uid,second.uid])

    def test_197_task_page_displays_both_progress_counts(self):
        s = state()
        s.add_generated_pet('100171',10)
        page = TaskPage(SimpleNamespace(state=s,data=DATA))
        self.assertIn('1/1 / 0/1',page.info())
        self.assertEqual((800,480),page.render().size)

    def test_197_guidance_locates_missing_pet_then_submit_npc(self):
        s = state()
        TaskProgress(s).update()
        resolver=GuideResolver(DATA,s)
        row=DATA.tables['MainTask']['197']
        target=resolver.from_task('main','197',row,s.main_state)
        self.assertIsNotNone(target)
        self.assertEqual('catch',target.kind)
        s.add_generated_pet('100171',10)
        s.add_generated_pet('100172',10)
        TaskProgress(s).update()
        target=resolver.from_task('main','197',row,s.main_state)
        self.assertEqual('160701',target.npc_id)


if __name__ == '__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(StoryFollowups))
    (OUT/'story-followups.json').write_text(json.dumps({'tests':result.testsRun,'errors':len(result.errors),'failures':len(result.failures)},indent=2),encoding='utf-8')
    sys.exit(not result.wasSuccessful())
