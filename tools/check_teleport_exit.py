"""Original old-man teleport, west exit, town arrival and live redraw callbacks."""
import unittest
from unittest.mock import patch
import check_single_window_flows as fixtures


class TeleportExitChecks(unittest.TestCase):
    setUp = fixtures.SingleWindowChecks.setUp
    tearDown = fixtures.SingleWindowChecks.tearDown
    click = fixtures.SingleWindowChecks.click

    def test_old_save_in_town_recovers_missed_plot_and_rewards_only_once(self):
        a = self.app
        a.state.main_task, a.state.main_state = 14, 4
        a.state.task_counts['main:14'] = [1]
        a.state.events['5901002'] = 1
        a.load_map(115, 3104, 1920)
        self.assertTrue(a.save())
        gold = a.state.count('700001')
        reward = int(a.data.tables['MainTask']['14']['rewardCounts'])
        self.assertTrue(a.restore())
        self.assertEqual(a.runtime.file, 'pEvent115001.json')
        self.assertEqual(a.state.task_counts['main:14'], [1])
        self.drain()
        self.assertEqual(a.state.count('700001'), gold+reward)
        self.assertEqual(a.state.main_task, 15)
        self.assertTrue(a.save())
        self.assertTrue(a.restore())
        self.assertFalse(a.runtime.running)
        self.assertEqual(a.state.count('700001'), gold+reward)
        self.assertEqual(a.state.completed_main.count(14), 1)

    def drain(self):
        a = self.app
        talks = []
        for _ in range(1000):
            self.assertFalse(a.runtime_error, a.runtime_error)
            if not a.runtime.running:
                return talks
            if a.ui_open:
                self.click('confirm_Button')
            elif a.display_request:
                talks.append(a.dialogue)
                a.make_frame()  # Exercise real sprites during the cutscene.
                a.interact()
            else:
                a.story_motion.advance(.1)
                a.advance_camera(.1)
                for timer in ('story_face_until', 'screen_fade_until', 'flash_until'):
                    if getattr(a, timer, 0):
                        setattr(a, timer, .01)
                a.drive()
        self.fail('Original story failed to finish')

    def test_original_teleport_west_exit_town_plot_and_redraw_keep_running(self):
        a = self.app
        a.state.main_task, a.state.main_state = 14, 3
        a.state.events['5901002'] = 1
        a.load_map(109, 2400, 3072)
        self.assertTrue(a.runtime.notify('tomap', map=109))
        a.drive()
        talks = self.drain()
        self.assertTrue(any('送蛋的老头' in t for t in talks if t))
        self.assertEqual(a.map_id, 114)
        self.assertEqual(a.state.events['109004'], 1)
        self.assertEqual(a.state.events['114001'], 1)
        a.exit_time = 0
        self.assertTrue(a.guide.start_click(32, 640))
        for _ in range(800):
            a.guide.step(.04)
            if a.map_id == 115:
                break
        self.assertEqual(a.map_id, 115)
        a.make_frame()  # Regression: blank TMX face crashed here.
        self.assertEqual(a.runtime.file, 'pEvent115001.json')
        self.assertEqual(a.state.main_state, 4)
        a.drive()
        talks = self.drain()
        self.assertTrue(any('那两个家伙' in t for t in talks if t))
        self.assertIn(14, a.state.completed_main)
        self.assertEqual(a.state.main_task, 15)
        self.assertEqual(a.state.events['115001'], 1)
        # A successful one-off render is insufficient: verify actual Tk ticks.
        errors, frames = [], []
        self.root.report_callback_exception = lambda *args: errors.append(args)
        for job in self.root.tk.call('after', 'info'):
            self.root.after_cancel(job)
        present = a.viewport.present
        def observe(frame):
            frames.append(frame.size)
            present(frame)
        with patch.object(a.viewport, 'present', observe):
            a.tick()
            self.root.after(250, self.root.quit)
            self.root.mainloop()
        self.assertFalse(errors, errors)
        self.assertGreater(len(frames), 3)
        before = a.x
        a.move_to(a.x-4, a.y)
        self.assertLess(a.x, before)

    def test_all_original_blank_face_actors_render_using_default_direction(self):
        a = self.app
        found = []
        for key in a.data.tables['VillageMap']:
            world = a.data.load_map(key)
            blank = [o for o in world.objects if o.get('gid') and o.get('props', {}).get('face') == '']
            if not blank:
                continue
            a.load_map(int(key))
            for obj in blank:
                sid = world.tile_properties(int(obj['gid']))['spriteId']
                self.assertEqual(a.actor_animation(obj['name'], sid), 'standdown')
                found.append((int(key), obj['name']))
            self.assertEqual(a.make_frame().size, (a.WIDTH, a.HEIGHT))
        self.assertEqual({mid for mid, _ in found}, {115, 305, 7801})


if __name__ == '__main__':
    unittest.main(verbosity=2)
