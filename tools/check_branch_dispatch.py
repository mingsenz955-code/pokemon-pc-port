"""No-window checks for real branch NPC dispatch and conversation branches."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from game_state import GameState
from event_runtime import EventRuntime
from branch_tasks import BranchTasks

DATA = OriginalData(ROOT/'original-1.20.4')


class BranchDispatchChecks(unittest.TestCase):
    def setUp(self):
        self.state = GameState(DATA.tables, 72)
        self.state.initialize(1)
        self.runtime = EventRuntime(DATA, self.state)

    def isolate(self, key, status):
        self.state.branch_states = {k: 5 for k in DATA.tables['BranchTask']}
        self.state.branch_states[str(key)] = status

    def test_prologue_team_does_not_leak_into_main_hero_collection(self):
        state = GameState(DATA.tables, 72)
        self.assertEqual(3, len(state.pets))
        self.assertTrue(state.encyclopedia)
        state.bank.append(state.pets.pop())
        state.rides = [1]
        state.ride = 1
        state.active_pet = 2
        state.initialize(1)
        self.assertEqual('尼尔', state.player_name)
        self.assertEqual([], state.pets)
        self.assertEqual([], state.bank)
        self.assertEqual([], state.encyclopedia)
        self.assertEqual([], state.rides)
        self.assertEqual(0, state.ride)
        self.assertEqual(0, state.active_pet)
        state.initialize(2)
        self.assertEqual(set(p.species for p in state.pets), set(state.encyclopedia))
        self.assertEqual(3, len(state.pets))

    def test_npc_selector_compares_conversation_not_fight_or_state(self):
        self.runtime.start('pEventBTask1001.json', npc_id=40608)
        self.assertTrue(self.runtime.branch_matches({'npcid': 40608, 'state': 0}))
        self.assertTrue(self.runtime.branch_matches({'npcid': 40608, 'state': 5}))
        self.state.npc_fights['580101'] = 1
        self.assertFalse(self.runtime.branch_matches({'npcid': 580101, 'state': 1}))

    def test_active_branch_target_enters_real_fight_and_result_branch(self):
        self.isolate(1001, 3)
        self.assertTrue(self.runtime.notify('talk', npcid=40608))
        self.assertEqual('pEventBTask1001.json', self.runtime.file)
        request = self.runtime.next()
        self.assertEqual(('fight', 16, 406081),
                         (request.kind, request.step, request.data['parameters']['npcid']))
        self.runtime.resume('lose')
        request = self.runtime.next()
        self.assertIsNone(request)  # Original step 18 is end, not a reward.
        self.assertEqual(3, self.state.branch_states['1001'])

    def test_giver_and_target_take_different_branches_in_same_script(self):
        self.isolate(1001, 3)
        self.state.main_task = 58
        self.assertTrue(self.runtime.notify('talk', npcid=580101))
        request = self.runtime.next()
        self.assertEqual(('talk', 14), (request.kind, request.step))
        self.assertIn('应该是真的', request.data['text'])

    def test_conversation_npc_survives_saved_pending_dialogue(self):
        self.isolate(1001, 3)
        self.state.main_task = 58
        self.runtime.notify('talk', npcid=580101)
        self.runtime.next()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'branch.json'
            self.state.save(path)
            state = GameState.load(DATA.tables, path)
            runtime = EventRuntime(DATA, state)
            runtime.restore(state.pending_runtime)
            self.assertEqual(580101, runtime.trigger_npc_id)
            self.assertTrue(runtime.branch_matches({'npcid': 580101}))
            runtime.resume()
            self.assertIsNone(runtime.next())
            self.assertEqual(0, runtime.trigger_npc_id)

    def test_available_branch_needs_every_prerequisite_pair(self):
        self.isolate(1001, 2)
        self.state.branch_states['901'] = 3
        self.state.main_task = 58
        branches = BranchTasks(self.state)
        self.assertFalse(branches.unlocked(DATA.tables['BranchTask']['1001']))
        self.assertEqual('901', branches.for_npc(580101))
        self.state.branch_states['901'] = 5
        self.assertEqual('1001', branches.for_npc(580101))
        self.state.main_task = 57
        self.state.main_state = 4
        self.assertIsNone(branches.for_npc(580101))

    def test_plot_trigger_still_precedes_branch_fallback(self):
        trigger = {'id': 999, 'type': 'talk', 'repeat': 0,
                   'conditions_add': {'npcid': 40608}}
        data = SimpleNamespace(event=lambda name: [trigger] if name == 'pEventContents.json' else [])
        self.isolate(1001, 3)
        runtime = EventRuntime(data, self.state)
        self.assertTrue(runtime.notify('talk', npcid=40608))
        self.assertEqual('pEvent999.json', runtime.file)

    def test_target_priority_then_state_descending_then_key_ascending(self):
        tables = copy.deepcopy(DATA.tables)
        base = tables['BranchTask']['1001']
        tables['BranchTask'] = {}
        for key, status, target in [('1001', 4, 0), ('1002', 3, 1), ('1003', 4, 1), ('1004', 4, 1)]:
            row = dict(base, keyId=key, dispatchNpcs='42', submitNpcs='42',
                       targetNpcs='42' if target else '99')
            tables['BranchTask'][key] = row
            self.state.branch_states[key] = status
        self.state.tables = tables
        self.assertEqual('1002', BranchTasks(self.state).for_npc(42))
        self.state.branch_states['1002'] = 5
        self.assertEqual('1001', BranchTasks(self.state).for_npc(42))

    def test_all_original_prerequisites_can_be_checked_without_crashing(self):
        branches = BranchTasks(self.state)
        for row in DATA.tables['BranchTask'].values():
            self.assertIsInstance(branches.unlocked(row), bool)
        self.assertTrue(branches.unlocked(dict(DATA.tables['BranchTask']['4801'], conditions_btask='0')))
        self.assertTrue(branches.unlocked(DATA.tables['BranchTask']['11401']))

    def test_branch_submission_advances_parent_quest_without_double_counting(self):
        from task_progress import TaskProgress
        self.state.branch_states = {'11501': 3, '11601': 4}
        TaskProgress(self.state).update()
        self.assertEqual([0, 0, 0, 0], self.state.task_counts['branch:11501'])
        self.state.submit_task(11601, branch=True)
        self.assertEqual([1, 0, 0, 0], self.state.task_counts['branch:11501'])
        self.state.submit_task(11601, branch=True)
        self.assertEqual([1, 0, 0, 0], self.state.task_counts['branch:11501'])
        for key in (11701, 11801, 11901):
            self.state.branch_states[str(key)] = 4
            self.state.submit_task(key, branch=True)
        self.assertEqual(4, self.state.branch_states['11501'])

    def test_illustrated_quest_counts_ever_owned_unique_species(self):
        from task_progress import TaskProgress
        self.state.branch_states = {'11401': 3}
        keys = list(DATA.tables['Pet'])[:99]
        self.state.encyclopedia = keys[:98]+keys[:3]
        TaskProgress(self.state).update()
        self.assertEqual([98], self.state.task_counts['branch:11401'])
        self.assertEqual(3, self.state.branch_states['11401'])
        self.state.record_pet(keys[-1])
        TaskProgress(self.state).update()
        self.assertEqual(4, self.state.branch_states['11401'])
        self.assertEqual([99], self.state.task_counts['branch:11401'])
        self.assertFalse(self.state.pets or self.state.bank)

    def test_parent_quest_guide_resolves_child_giver_or_submission_npc(self):
        from guide import GuideResolver
        resolver = GuideResolver(DATA, self.state)
        row = DATA.tables['BranchTask']['11501']
        self.state.branch_states = {'11501': 3, '11601': 4}
        target = resolver.from_task('branch', '11501', row, 3)
        self.assertEqual('npc', target.kind)
        self.assertEqual('11501', target.task_id)
        self.assertIn('11601', target.detail)
        self.assertEqual(DATA.tables['BranchTask']['11601']['submitNpcs'], target.npc_id)

    def test_illustrated_guide_does_not_invent_a_pet_location(self):
        from guide import GuideResolver
        self.state.encyclopedia = []
        target = GuideResolver(DATA, self.state).from_task('branch', '11401', DATA.tables['BranchTask']['11401'], 3)
        self.assertEqual(('pet', 0), (target.kind, target.map_id))
        self.assertIn('0/99', target.detail)


if __name__ == '__main__':
    unittest.main(verbosity=2)
