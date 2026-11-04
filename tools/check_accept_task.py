"""Actual native accept card, cancellation, pet selection and persisted hand-in."""
import unittest
from check_sunshine_quests import SunshineQuestChecks

if __name__ == '__main__':
    suite = unittest.TestSuite(SunshineQuestChecks(name) for name in (
        'test_jia_accept_cancel_select_pet_and_claim_once',
        'test_bank_pet_handover_survives_save_restore_and_excludes_trial'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
