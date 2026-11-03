"""Native hatch condition/actions; shared isolated page regression cases."""
import unittest
from check_counter_hatching import CounterHatchChecks

if __name__ == '__main__':
    suite = unittest.TestSuite(CounterHatchChecks(name) for name in (
        'test_material_conditions_errors_and_take_back_preserve_items',
        'test_nested_hatch_check_returns_without_advancing_original_npc_script'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
