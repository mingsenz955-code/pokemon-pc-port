"""The PC edition allows manual hatching and no longer forces tutorial clicks."""
import unittest
import check_mount_tutorial as checks

class HatchTutorialChecks(checks.MountTutorialChecks):
    def test_cancel_hatch_room_is_allowed_without_a_guided_button(self):
        from event_runtime import Request
        a = self.app
        a.open_ui(Request('openui', 'manual-hatch', 0, {'parameters': {'uiid': 5}}))
        self.assertTrue(a.ui_open)
        self.assertFalse(a.ui_tutorial_active)
        a.ui_window._close()
        self.assertFalse(a.ui_open)
        self.assertIsNone(a.display_request)

    def test_normal_hatch_still_charges_gold(self):
        from activities import Activities
        a = self.app
        a.state.grant('250001', 1)
        activity = Activities(a.state)
        activity.put_egg(0, '250001')
        before = a.state.count('700001')
        cost = int(a.data.tables['HatchItem']['250001']['moneyCount'])
        activity.hatch(0, use_money=True)
        self.assertEqual(a.state.count('700001'), before-cost)

if __name__ == '__main__':
    unittest.main(verbosity=2)
