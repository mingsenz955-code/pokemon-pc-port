"""PR 13: safe transport, live free-draw eligibility, and modal wheel restore."""
import os
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from pc_game import NativeGame
from event_runtime import Request
from game_state import numbers

DATA = OriginalData(ROOT/'original-1.20.4')


class ReviewChecks(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.previous = os.environ.get('POCKET_NATIVE_SAVE_DIR')
        os.environ['POCKET_NATIVE_SAVE_DIR'] = self.folder.name
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = NativeGame(self.root, DATA)
        a = self.app
        a.runtime.file, a.runtime.sequence, a.runtime.pending = '', [], None
        a.display_request, a.pending_wait = None, None

    def tearDown(self):
        self.app.close_ui()
        for job in self.root.tk.call('after', 'info'):
            self.root.after_cancel(job)
        self.root.destroy()
        self.folder.cleanup()
        if self.previous is None:
            os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
        else:
            os.environ['POCKET_NATIVE_SAVE_DIR'] = self.previous

    def open(self, uid):
        self.app.open_ui(Request('openui', 'review-check', 1, {'parameters': {'uiid': uid}}))
        self.app.ui_window.withdraw()

    def test_all_item_destinations_use_safe_original_entry_points(self):
        a = self.app
        for mid in numbers(DATA.tables['FunctionItem']['220001']['parameters']):
            with self.subTest(map=mid):
                world = DATA.load_map(mid)
                x, y = a._transport_arrival(mid)
                self.assertFalse(world.blocked(x, y))
                entries = [obj for obj in world.objects if obj.get('group') == 'spriteLayer'
                           and not obj.get('gid') and str(obj.get('name')) == str(mid*100+1)
                           and obj.get('props', {}).get('toExit')]
                if entries:
                    self.assertEqual(a.exit_spawn(world, entries[0]), (x, y))

    def test_real_transport_callback_spends_once_and_stops_old_route(self):
        a = self.app
        a.load_map(102)
        a.state.visited_maps, a.state.inventory = [101, 102], {'220001': 2}
        expected = a._transport_arrival(101)
        self.open(46)
        a.ui_actions['use_Button']()
        # Plot outcomes are outside this navigation-only test. The real map
        # load, item consumption and collision lookup are not mocked.
        with patch.object(a.runtime, 'notify'), patch.object(a, 'drive'):
            a.ui_actions['item_flight_101']()
        self.assertEqual(101, a.map_id)
        self.assertEqual(expected, (a.x, a.y))
        self.assertFalse(a.map.blocked(a.x, a.y))
        self.assertEqual(1, a.state.count('220001'))
        self.assertFalse(a.guide.active)

    def test_invalid_destination_does_not_spend_item_or_change_map(self):
        a = self.app
        a.load_map(102)
        a.state.visited_maps, a.state.inventory = [101, 102], {'220001': 2}
        before = a.map_id, a.x, a.y
        self.open(46)
        a.ui_actions['use_Button']()
        blocked_world = SimpleNamespace(width=2, height=2, objects=[], blocked=lambda *_: True)
        with patch.object(a.data, 'load_map', return_value=blocked_world):
            a.ui_actions['item_flight_101']()
        self.assertEqual(before, (a.map_id, a.x, a.y))
        self.assertEqual(2, a.state.count('220001'))
        self.assertEqual('TipConfirmUI', a.original_page.specs[0][0])

    def test_expiring_free_draw_is_rechecked_at_click_and_next_draw_is_paid(self):
        a = self.app
        a.state.functions['8'] = 1
        a.state.inventory['700002'] = 1000
        a.state.activities['lucky_free_at'] = 1005
        with patch('original_pages.time.time', return_value=1000) as clock:
            self.open(68)
            before = len(a.state.pets)+len(a.state.bank)
            clock.return_value = 1005
            a.ui_actions['draw_1_Button']()
            self.assertEqual(1000, a.state.count('700002'))
            self.assertEqual(before+1, len(a.state.pets)+len(a.state.bank))
            self.assertGreater(a.state.activities['lucky_free_at'], 1005)
            a.ui_actions['confirm_Button']()
            a.ui_actions['draw_1_Button']()
            self.assertEqual(990, a.state.count('700002'))
            self.assertEqual(before+2, len(a.state.pets)+len(a.state.bank))

    def test_closing_login_reward_restores_page_wheel_without_reopening_reward(self):
        a = self.app
        self.open(12)
        wheel = a.page_wheel
        row = DATA.tables['ContinuousLogin']['1']
        before = a.state.count(row['rewardKid'])
        a.ui_actions['get_Button']()
        self.assertTrue(a.reward_visible)
        self.assertIsNot(wheel, a.page_wheel)
        a.ui_actions['confirm_Button']()
        self.assertIs(wheel, a.page_wheel)
        a.page_wheel(SimpleNamespace(delta=-120))
        self.assertFalse(a.reward_visible)
        self.assertEqual('ContinuousLoginUI', a.original_page.specs[0][0])
        self.assertEqual(before+int(row['rewardCount']), a.state.count(row['rewardKid']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
