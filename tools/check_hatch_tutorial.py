"""Original 5905001 story, actual page clicks and timers, isolated saves."""
import time
import unittest
from types import SimpleNamespace
import check_counter_hatching as fixtures


class HatchTutorialChecks(fixtures.CounterHatchChecks):
    def test_saved_old_lesson_with_already_hatched_egg_resumes_at_claim(self):
        from activities import Activities
        self.begin_story()
        a = self.app
        # Old build allowed manual hatch while still waiting for its first tip.
        Activities(a.state).put_egg(0, '250001')
        pet = Activities(a.state).hatch(0, use_money=True)
        original_uid = pet.uid
        original_money = a.state.count('700001')
        a.state.main_task, a.state.main_state = 10, 3
        self.assertTrue(a.save())
        self.assertTrue(a.restore())
        self.assertTrue(a.ui_open)
        self.assertEqual(a.display_request.data['nodekey'], 'takeBack_Button_1')
        self.assertEqual(a.state.count('700001'), original_money)
        self.guided_click('takeBack_Button_1')
        self.assertEqual(sum(p.uid == original_uid for p in a.state.pets+a.state.bank), 1)
        self.click('confirm_Button')
        self.guided_click('close_Button')
        self.assertIn('欢迎下次光临', a.dialogue)

    def test_free_lesson_is_single_use_and_normal_hatch_still_costs_gold(self):
        from activities import Activities
        self.begin_story()
        a = self.app
        self.guided_click('putIn_Button_1')
        self.guided_click('hatchRoomChooseItem_250001')
        self.guided_click('check_Button_1')
        self.guided_click('hatch_Button')
        self.assertTrue(a.state.activities['hatch_tutorial_free_used'])
        a.state.grant('250001', 1)
        activity = Activities(a.state)
        activity.put_egg(1, '250001')
        before = a.state.payload()
        with self.assertRaises(ValueError):
            activity.hatch(1, free_tutorial=True)
        self.assertEqual(a.state.payload(), before)
        money = a.state.count('700001')
        activity.hatch(1, use_money=True)
        self.assertEqual(a.state.count('700001'), money-int(a.data.tables['HatchItem']['250001']['moneyCount']))

    def settle(self):
        end = time.monotonic()+2
        while self.app.pending_wait and time.monotonic() < end:
            self.root.update()
            time.sleep(.01)
        self.assertIsNone(self.app.pending_wait)

    def begin_story(self):
        a = self.app
        self.reset_script()
        a.state.main_task, a.state.main_state = 10, 3
        a.state.events['5905001'] = 0
        a.state.grant('250001', 1)  # Original old man's gift in pEvent105002.
        a.load_map(5905, 352, 480)
        a.play_event('pEvent5905001.json')
        for _ in range(300):
            if a.ui_open:
                break
            a.story_motion.advance(.1)
            a.drive()
            if a.display_request and a.display_request.kind == 'talk':
                a.interact()
        self.assertTrue(a.ui_open)
        self.assertEqual(a.runtime_error, '')

    def guided_click(self, key):
        a = self.app
        self.settle()
        self.assertEqual(a.display_request.data['nodekey'], key)
        target = a._ui_tutorial_target(key)
        self.assertIsNotNone(target, key)
        self.click(target)

    def test_original_story_hatches_claims_submits_and_opens_lottery(self):
        self.begin_story()
        a = self.app
        pending = a.runtime.pending
        self.click('close_Button')
        a.ui_window._close()  # Esc/window-close must not strand a running lesson.
        self.assertTrue(a.ui_open)
        self.assertIs(a.runtime.pending, pending)
        self.guided_click('putIn_Button_1')
        self.guided_click('hatchRoomChooseItem_250001')
        self.assertEqual(a.state.activities['eggs']['0']['item'], '250001')
        self.guided_click('check_Button_1')
        before = a.state.count('700001')
        self.guided_click('hatch_Button')
        self.assertEqual(a.state.count('700001'), before)  # Original free tutorial.
        egg = a.state.activities['eggs']['0']
        self.assertIsNotNone(egg['pet'])
        self.settle()
        self.assertEqual(a.display_request.data['nodekey'], 'confirm_Button')
        page = a.original_page
        self.click('confirm_Button')
        self.assertIs(a.original_page, page)
        self.assertEqual(a.display_request.data['nodekey'], 'confirm_Button')
        errors = []
        self.root.report_callback_exception = lambda *args: errors.append(args)
        page.effect_start -= 4
        self.root.after(140, self.root.quit)
        self.root.mainloop()
        self.assertFalse(errors, errors)
        self.guided_click('confirm_Button')
        count = len(a.state.pets+a.state.bank)
        self.guided_click('takeBack_Button_1')
        self.assertEqual(len(a.state.pets+a.state.bank), count+1)
        self.assertNotIn('0', a.state.activities['eggs'])
        self.click('confirm_Button')  # Actual obtained-pet reward popup.
        self.guided_click('close_Button')
        self.assertFalse(a.ui_open)
        self.assertIn('欢迎下次光临', a.dialogue)
        a.interact()
        if a.ui_open:  # Submit-task reward.
            self.click('confirm_Button')
        self.assertIn(10, a.state.completed_main)
        self.assertEqual(a.state.events['5905001'], 1)
        self.assertEqual(a.state.functions['8'], 1)
        self.assertEqual(a.display_request.data['nodekey'], 'draw_Button')
        a.scene_ui.render(a.make_frame())
        rect = a.scene_ui.hits['draw_Button']
        a.on_click(SimpleNamespace(x=(rect[0]+rect[2])/2, y=(rect[1]+rect[3])/2))
        self.settle()
        self.assertEqual(a.display_request.data['nodekey'], 'draw_1_Button')
        self.assertIsNotNone(a._ui_tutorial_target('draw_1_Button'))
        self.assertFalse(a.runtime_error)


if __name__ == '__main__':
    unittest.main(verbosity=2)
