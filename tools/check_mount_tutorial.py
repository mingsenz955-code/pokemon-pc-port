"""Real original merchant event, terrain interaction and exit artwork."""
import unittest
from types import SimpleNamespace
import check_single_window_flows as fixtures
from event_runtime import Request
from exit_markers import exit_markers


class MountTutorialChecks(unittest.TestCase):
    setUp = fixtures.SingleWindowChecks.setUp
    tearDown = fixtures.SingleWindowChecks.tearDown
    click = fixtures.SingleWindowChecks.click

    def test_all_three_merchants_finish_without_teaching_waits(self):
        a = self.app
        for map_id, filename in [(202, 'pEvent202001.json'), (315, 'pEvent315002.json'), (403, 'pEvent403002.json')]:
            with self.subTest(map=map_id):
                a.load_map(map_id)
                a.play_event(filename)
                opened = False
                for _ in range(2000):
                    self.assertFalse(a.runtime_error, a.runtime_error)
                    self.assertIsNone(a.pending_wait)
                    self.assertEqual(a.state.trial_ride, 0)
                    if a.ui_open:
                        self.assertEqual(a.original_page.specs[0][0], 'BuyPetUI')
                        opened = True
                        a.ui_window._close()
                    elif a.display_request:
                        self.assertNotEqual(a.display_request.kind, 'button')
                        a.interact()
                    elif not a.runtime.running:
                        break
                    else:
                        a.story_motion.advance(.1)
                        a.advance_camera(.1)
                        a.drive()
                self.assertTrue(opened)
                self.assertFalse(a.runtime.running)
                self.assertFalse(a.teach_nodes)

    def test_old_pending_rock_wait_save_is_released(self):
        a = self.app
        a.load_map(202, 21*64+32, 25*64+32)
        a.runtime.start('pEvent202001.json')
        a.runtime.index = next(i for i, row in enumerate(a.runtime.sequence) if row['id'] == 21)
        a.runtime.pending = Request('wait', a.runtime.file, 21, a.runtime.sequence[a.runtime.index])
        a.state.trial_ride = 500005
        a.teach_nodes = [{'state': 1, 'x': 24, 'y': 23}]
        a.main_ui_visible = False
        self.assertTrue(a.save())
        self.assertTrue(a.restore())
        self.assertIsNone(a.pending_wait)
        self.assertEqual(a.state.trial_ride, 0)
        self.assertTrue(a.main_ui_visible)
        self.assertFalse(a.teach_nodes)
        self.assertIn('坐骑商人', a.dialogue)

    def test_all_original_buttons_and_terrain_lessons_are_removed(self):
        from offline_tutorials import removed_tutorial_step
        count = 0
        for path in (self.app.data.root/'events').glob('*.json'):
            if path.name == 'pEventContents.json':
                continue
            for row in self.app.data.event(path.name):
                if row['type'] in ('button', 'addteachnode', 'trialride') or (row['type'] == 'wait' and row.get('parameters', {}).get('type') == 3):
                    self.assertTrue(removed_tutorial_step(path.name, row), (path.name, row))
                    count += 1
        self.assertGreater(count, 0)

    def test_manual_hatch_has_no_forced_clicks_and_keeps_free_first_hatch(self):
        a = self.app
        a.state.main_task, a.state.main_state = 10, 3
        a.state.grant('250001', 1)
        a.load_map(5905, 352, 480)
        a.play_event('pEvent5905001.json')
        for _ in range(300):
            if a.ui_open:
                break
            if a.display_request:
                a.interact()
            else:
                a.story_motion.advance(.1)
                a.drive()
        self.assertTrue(a.ui_open)
        self.assertIsNone(a.display_request)
        self.assertFalse(a.ui_tutorial_active)
        self.click('hatch_0/Layer/root_Panel/putIn_Button')
        self.click('chooseItem_250001')
        self.click('hatch_0/Layer/root_Panel/check_Button')
        before = a.state.count('700001')
        self.click('moneyHatch_Button')
        self.assertEqual(a.state.count('700001'), before)
        self.assertIsNotNone(a.state.activities['eggs']['0']['pet'])
        a.ui_window._close()
        self.assertFalse(a.runtime_error)

    def test_original_exit_artwork_four_directions_and_wide_gate(self):
        a = self.app
        for face in range(1, 5):
            world = SimpleNamespace(tw=64, th=64, objects=[dict(group='spriteLayer', x=0, y=0,
                width=384, height=384, props={'toExit': '10201', 'face': face})])
            markers = list(exit_markers(world))
            self.assertEqual(len(markers), 3)
            image, _ = a.exit_arrow_frame(markers[0][2], 0)
            self.assertIsNotNone(image.getbbox())

    def test_missing_spine_folder_pet_and_map_actor_load(self):
        d = self.app.data
        self.assertGreater(d.pet_clip_duration('100162', 'stand'), 0)
        self.assertIsNotNone(d.pet_image('100162'))
        self.assertIsNotNone(d.pet_frame('100162', 'stand', 7))
        self.assertIsNotNone(d.village_sprite('21065'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
