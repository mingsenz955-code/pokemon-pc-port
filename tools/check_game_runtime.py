"""Check original trigger conditions, transaction boundaries and mid-event save/restore."""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from game_state import GameState
from event_runtime import EventRuntime, PendingMechanic

data = OriginalData(ROOT/'original-1.20.4')
state = GameState(data.tables, 2400501419)
runtime = EventRuntime(data, state)
assert state.initialization == 2 and len(state.pets) == 3
assert state.main_matches(1, 3)
assert state.main_matches(2, 2) and not state.main_matches(2, 5)
state.main_task = 10
assert state.main_matches(2, 5) and not state.main_matches(2, 3)
assert runtime.matches({'id': 99999999, 'conditions_mtask': [2, 3, 2, 5]})
assert not runtime.matches({'id': 99999999, 'conditions_event': [123, 1, 124, 0]})
state.events['123'] = 1
assert runtime.matches({'id': 99999999, 'conditions_event': [123, 1, 124, 0]})
state.main_task, state.main_state = 1, 3

assert runtime.notify('tomap', map=7401)
assert runtime.file == 'pEvent7401001.json'
for kind in ['screenclose', 'screenmove', 'toplace', 'aside']:
    request = runtime.next()
    assert request.kind == kind, (request, kind)
    if kind != 'aside':
        runtime.resume()
assert request.data['text'] == '十年前迪尼斯城'

with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)/'slot1.json'
    snapshot = runtime.snapshot()
    next_random = state.rng.getstate()
    state.save(path)
    restored_state = GameState.load(data.tables, path)
    restored = EventRuntime(data, restored_state)
    restored.restore(restored_state.pending_runtime)
    assert restored.snapshot() == snapshot
    assert restored.next().data['text'] == '十年前迪尼斯城'
    assert restored_state.rng.getstate() == next_random
    restored.resume()
    assert restored.next().data['text'] == '第五届宠物联盟训练师冠军赛'

state.initialize(1)
assert not state.pets and state.inventory['700001'] == 100
state.add_preset(2)
assert state.pets[0].species == data.tables['InitPet']['2']['petId']
before = state.inventory.copy()
try:
    state.consume(['700001', '700001'], [60, 60])
    raise AssertionError('Costs were not aggregated')
except ValueError:
    assert state.inventory == before
state.submit_task(1)
assert state.main_task == 2 and state.inventory['700001'] == 1100
assert state.submit_task(1) is False and state.inventory['700001'] == 1100

runtime = EventRuntime(data, state)
runtime.start('pEvent101002.json')
assert runtime.branch_matches({'initid': 1, 'id': 7})
assert not runtime.branch_matches({'initid': 2, 'id': 11})
try:
    runtime.branch_matches({'npcid': 10101, 'state': 1, 'id': 2})
    raise AssertionError('Unverified NPC-state branch silently passed')
except PendingMechanic:
    pass
runtime.pending = None
runtime.file = ''
runtime.start('pEvent1002001.json')
runtime.index = next(i for i, s in enumerate(runtime.sequence) if s['type'] == 'fight')
request = runtime.next()
assert request.kind == 'fight'
try:
    runtime.resume()
    raise AssertionError('Missing battle outcome was accepted')
except ValueError:
    assert runtime.pending is request
runtime.resume('lose')
request = runtime.next()
assert state.events['1002001'] == 0 and state.main_task == 2

report = {'original_trigger_rows': len(runtime.triggers),
          'task_condition_semantics_from_binary': 'passed',
          'real_prologue_starts_in_7401': 'passed',
          'mid_dialogue_save_and_rng_round_trip': 'passed',
          'cost_aggregation_no_partial_deduction': 'passed',
          'task_rewards_cannot_repeat': 'passed',
          'unverified_npc_state_branch_stops': 'passed',
          'battle_without_outcome_cannot_continue': 'passed',
          'native_host_full_gameplay': 'partial: prologue→starter→main task 4 verified in Tk host; later systems pending'}
(ROOT/'outputs/verification/game-runtime-checks.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
