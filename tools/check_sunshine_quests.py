"""Real branch acceptance/hand-in and original sunshine rescue story chain."""
import copy
import json
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
import check_single_window_flows as fixtures
from event_runtime import EventRuntime
from game_state import GameState
from task_costs import TaskCosts
from task_progress import TaskProgress
from area_order import native_area_order

OUT = Path(__file__).resolve().parent.parent/'outputs/verification/sunshine-story'
OUT.mkdir(parents=True, exist_ok=True)


class SunshineQuestChecks(unittest.TestCase):
    setUp = fixtures.SingleWindowChecks.setUp
    tearDown = fixtures.SingleWindowChecks.tearDown
    click = fixtures.SingleWindowChecks.click

    def finish(self, limit=3000):
        a = self.app
        talks = []
        for _ in range(limit):
            # Scene fades/faces use monotonic deadlines. Pump the actual Tk
            # timers rather than exhausting 3000 CPU-only iterations before
            # a normal 0.4-second transition can finish.
            self.root.update()
            if max(getattr(a,'screen_fade_until',0), getattr(a,'story_face_until',0),
                   getattr(a,'wait_until',0)) > time.monotonic():
                time.sleep(.003)
            self.assertFalse(a.runtime_error, a.runtime_error)
            if a.battle:
                battle = a.battle
                for _ in range(200):
                    if battle.result:
                        break
                    if battle.force_switch:
                        battle.choose_switch(next(i for i, p in enumerate(battle.player) if p.alive))
                    else:
                        battle.choose_skill(0)
                self.assertEqual(battle.result, 'win')
                a.finish_battle()
            elif a.ui_story_active and a.display_request:
                a.paint_modal_story()
                a.on_ui_click(SimpleNamespace(x=400, y=440))
            elif a.ui_open:
                self.click('confirm_Button')
            elif a.display_request:
                talks.append(a.dialogue or '')
                a.make_frame()
                a.interact()
            elif not a.runtime.running:
                return talks
            else:
                a.advance_camera(.1)
                a.story_motion.advance(.1)
                a.drive()
        self.fail(f'Original event stopped at {a.runtime.file}:{a.runtime.index}')

    def test_jia_accept_cancel_select_pet_and_claim_once(self):
        a = self.app
        a.state.main_task, a.state.main_state = 15, 3
        a.load_map(115, 2400, 2048)
        pet = a.state.add_generated_pet('100017')
        spare = a.state.add_generated_pet('100017')
        a.interact('11502')
        for _ in range(3):
            a.interact()
        self.assertEqual(a.original_page.specs[0][0], 'AcceptBTaskUI')
        self.click('accept_Button')
        self.finish()
        TaskProgress(a.state).update()
        self.assertEqual(a.state.branch_states['3101'], 4)
        a.interact('11502')
        self.assertEqual(a.original_page.specs[0][0], 'MultipleChoicePetUI')
        a.ui_window._close()
        self.assertFalse(a.runtime.running)
        self.assertIn(pet, a.state.pets)
        a.interact('11502')
        self.click('confirm_Button')  # Incomplete selection does not consume.
        self.assertEqual(a.original_page.specs[0][0], 'TipConfirmUI')
        self.click('confirm_Button')
        self.click('handin_pet_'+pet.uid)
        before = a.state.count('700001')
        self.click('confirm_Button')
        self.finish()
        self.assertNotIn(pet, a.state.pets+a.state.bank)
        self.assertIn(spare, a.state.pets)
        self.assertEqual(a.state.branch_states['3101'], 5)
        self.assertEqual(a.state.count('700001'), before+500)
        self.assertEqual(a.state.completed_branch.count(3101), 1)
        self.assertFalse(a.runtime_error)

    def test_bank_pet_handover_survives_save_restore_and_excludes_trial(self):
        a = self.app
        a.state.main_task, a.state.main_state = 15, 3
        a.load_map(115, 2400, 2048)
        bank = a.state.add_generated_pet('100017')
        a.state.move_pet(bank.uid, to_bank=True)
        trial = a.state.add_generated_pet('100017')
        trial.trial_id = 'test-only'
        a.state.branch_states['3101'] = 4
        a.interact('11502')
        self.assertFalse(any(key == 'handin_pet_'+trial.uid for key in a.ui_hits))
        self.assertTrue(a.save())
        self.assertTrue(a.restore())
        self.assertEqual(a.original_page.specs[0][0], 'MultipleChoicePetUI')
        self.click('handin_pet_'+bank.uid)
        self.click('confirm_Button')
        self.finish()
        self.assertFalse(any(p.uid == bank.uid for p in a.state.bank))
        self.assertTrue(any(p.uid == trial.uid for p in a.state.pets))
        self.assertEqual(a.state.branch_states['3101'], 5)

    def test_old_ready_area_counter_resumes_original_plot_at_actual_goal(self):
        a = self.app
        a.state.main_task, a.state.main_state = 15, 4
        a.state.task_counts['main:15'] = [1]
        a.state.events['115001'] = 1
        a.load_map(115, 1376, 480)
        a.process_player_areas(force=True)
        a.drive()
        self.assertEqual(a.runtime.file, 'pEvent115002.json')
        self.finish()
        self.assertIn(15, a.state.completed_main)
        self.assertEqual(a.state.main_task, 16)
        self.assertEqual(a.state.events['115002'], 1)

    def test_missing_item_cost_can_be_dismissed_without_locking_conversation(self):
        a = self.app
        a.state.main_task, a.state.main_state = 15, 3
        a.load_map(115)
        # Original Beta task requires five balls; emulate a stale ready status.
        a.state.inventory['220004'] = 0
        a.runtime.start('pEventBTask3301.json', npc_id=11504)
        step = next(row for row in a.runtime.sequence if row['type'] == 'costtaskitem')
        a.runtime.jump(step['id'])
        a.drive()
        self.assertEqual(a.original_page.specs[0][0], 'TipConfirmUI')
        a.ui_window._close()
        self.assertFalse(a.ui_open or a.runtime.running or a.runtime_error)
        self.assertNotIn(3301, a.state.completed_branch)

    def test_complete_original_rescue_letters_map_dialogue_and_sailing(self):
        a = self.app
        a.state.main_task, a.state.main_state = 14, 3
        a.state.events['5901002'] = 1
        a.state.grant('270045', 1)
        a.state.add_preset(201)
        a.state.active_pet = 1
        a.load_map(115, 3104, 1920)
        self.assertTrue(a.runtime.notify('tomap', map=115))
        a.drive()
        self.finish()
        self.assertEqual(a.state.main_task, 15)
        a.x, a.y = 1376, 480  # Outer follow-the-team area.
        a.process_player_areas(force=True)
        a.drive()
        self.finish()
        self.assertEqual(a.state.main_task, 16)
        a.x, a.y = 1504, 608  # Inner rescue area, inside the outer area too.
        a.process_player_areas(force=True)
        a.drive()
        self.finish()
        self.assertEqual(a.state.main_task, 17)
        self.assertEqual(a.map_id, 201)
        self.assertEqual(a.state.events['115003'], 1)
        self.assertEqual(a.state.count('270045'), 0)
        self.assertEqual(a.state.count('270011'), 1)
        self.assertTrue(any(p.species == '100038' for p in a.state.pets+a.state.bank))
        self.assertTrue(a.player_visible)
        self.assertFalse(a.ui_open or a.runtime.running or a.runtime_error)
        self.assertIn(203, [a.state.world_focus])
        self.assertEqual(a.make_frame().size, (a.WIDTH, a.HEIGHT))

    def test_live_map_story_keeps_refreshing_and_responds_to_dialogue_clicks(self):
        a = self.app
        a.state.main_task, a.state.main_state = 16, 3
        a.load_map(115)
        a.runtime.start('pEvent115003.json')
        a.runtime.jump(64)  # Independently exercise the original map scene.
        a.drive()
        self.assertTrue(a.ui_story_active)
        self.assertEqual(a.display_request.step, 65)
        for job in self.root.tk.call('after', 'info'):
            self.root.after_cancel(job)
        errors, frames = [], []
        self.root.report_callback_exception = lambda *args: errors.append(args)
        set_layer = a.ui_art_label.set_layer
        def observe(frame):
            frames.append(frame.size)
            set_layer(frame)
        a.ui_art_label.set_layer = observe
        a.tick()
        self.root.after(100, lambda: a.on_ui_click(SimpleNamespace(x=400, y=440)))
        self.root.after(300, self.root.quit)
        self.root.mainloop()
        self.assertFalse(errors, errors)
        self.assertGreater(len(frames), 3)
        self.assertEqual(a.display_request.step, 67)
        self.assertEqual(a.state.world_focus, 203)
        a.ui_base_layer.save(OUT/'map-dialogue.png')
        a.on_ui_click(SimpleNamespace(x=400, y=440))
        self.assertFalse(a.ui_open or a.ui_story_active)
        self.assertEqual(a.display_request.step, 69)

    def test_all_original_task_cost_rows_support_real_pet_and_item_handover(self):
        tables = self.app.data.tables
        for table in ('MainTask', 'BranchTask'):
            for key in tables[table]:
                state = GameState(tables, seed=77)
                state.initialize(1)
                state.main_task = int(key) if table == 'MainTask' else 15
                args = {'btask': int(key)} if table == 'BranchTask' else {'mtask': 1}
                cost = TaskCosts(state, args)
                selected = []
                for species, count in cost.pets.items():
                    for _ in range(count):
                        selected.append(state.add_generated_pet(species).uid)
                for item, count in cost.items.items():
                    state.grant(item, count)
                with self.subTest(table=table, task=key):
                    cost.consume(selected)
                    self.assertFalse(any(p.uid in selected for p in state.pets+state.bank))

    def test_all_original_signed_giveitem_commands_remove_without_freezing(self):
        data = self.app.data
        found = 0
        for path in (data.root/'events').glob('*.json'):
            for step in json.loads(path.read_text(encoding='utf-8')):
                if step['type'] != 'giveitem':
                    continue
                rows = step['parameters'] if isinstance(step['parameters'], list) else [step['parameters']]
                if not any(r['itemcount'] < 0 for r in rows):
                    continue
                state = GameState(data.tables, seed=78)
                state.initialize(1)
                for row in rows:
                    if row['itemcount'] < 0:
                        self.assertNotIn(str(row['itemid']), data.tables['Pet'])
                        state.grant(row['itemid'], 2)
                adapter = SimpleNamespace(event=lambda name: [] if name == 'pEventContents.json' else [step])
                runtime = EventRuntime(adapter, state)
                runtime.start(path.name)
                self.assertIsNone(runtime.next())
                self.assertFalse(runtime.running)
                for row in rows:
                    if row['itemcount'] < 0:
                        self.assertEqual(state.count(row['itemid']), max(0, 2+row['itemcount']))
                found += 1
        self.assertGreater(found, 10)

    def test_native_area_bucket_collision_and_rehash_order(self):
        objects = [{'group': 'eventLayer', 'name': str(i)} for i in (1, 12, 2)]
        self.assertEqual([r['name'] for r in native_area_order(objects)], ['2', '12', '1'])
        objects += [{'group': 'eventLayer', 'name': str(i)} for i in range(3, 15) if i != 12]
        self.assertEqual(len(native_area_order(objects)), len(objects))
        for key in self.app.data.tables['VillageMap']:
            original = self.app.data.load_map(key).objects
            result = native_area_order(original)
            self.assertEqual(len(result), len({r['name'] for r in original if r['group'] == 'eventLayer'}))

    def test_all_original_duplicate_labels_have_unambiguous_jump_targets(self):
        data = self.app.data
        checked = 0
        for path in (data.root/'events').glob('*.json'):
            sequence = json.loads(path.read_text(encoding='utf-8'))
            if len({row['id'] for row in sequence}) == len(sequence):
                continue
            runtime = EventRuntime(data, self.app.state)
            runtime.start(path.name)
            self.assertEqual(runtime.sequence, sequence)
            checked += 1
        self.assertEqual(checked, 18)


if __name__ == '__main__':
    unittest.main(verbosity=2)
