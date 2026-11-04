"""Infinite Arena (无限竞技场) data, state, real UI and event contract.

Original event pEventTalk790101:
    openui 20 par1=1 -> closeui no=7/yes=9
    yes -> fight {type:5, npcid:1} -> fightover win=11/lose=13

`npcid` is the InfiniteArena id; the persisted floor selects IArenaNpc
Lv.30/60/90/120/121.  Formula_InfiniteArenaHonorReward is a 4-byte ARM stub
returning 1, so each win grants one 700007 honour.
"""
import json
import sys
import tempfile
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))

from game_state import GameState  # noqa: E402
from infinite_arena import InfiniteArenaProgress, make_infinite_arena_battle  # noqa: E402
from original_data import OriginalData  # noqa: E402
from pc_game import NativeGame  # noqa: E402

data = OriginalData(ROOT/'original-1.20.4')
tables = data.tables
state = GameState(tables)
state.grant('700002', 3)
progress = InfiniteArenaProgress(state)
assert [row['petLevel'] for row in progress.levels()] == ['30', '60', '90', '120', '121']
assert progress.entry_cost('1') == ('700002', 1)
assert progress.level('1') == 1
assert progress.highest() == 1
assert progress.honor() == 0

progress.enter('1')
assert state.count('700002') == 2
battle = make_infinite_arena_battle(tables, state.pets, '1', state.rng, level=1)
assert battle.kind == 'infinite_arena' and len(battle.enemy) == 6
assert all(unit.pet.level == 30 for unit in battle.enemy)
assert not battle.can_catch and not battle.can_escape
assert all(unit.pet.species in tables['Pet'] for unit in battle.enemy)

summary = progress.finish('win')
assert summary['level_before'] == 1 and summary['level_after'] == 2
assert summary['honor_after'] == 1 and state.count('700007') == 1
assert state.arenas['1'] == 1 and state.infinite_highest == 2

# Level 5 is the cap; a loss resets the event state but keeps the honor.
state.infinite_level = 5
progress.enter('1')
progress.finish('lose')
assert state.infinite_level == 5
assert state.arenas['1'] == 0
assert state.count('700007') == 1

# Old 0.2.3 save gains the new fields.
old = GameState(tables)
old.grant('700002', 1)
payload = old.payload()
for key in ('infinite_level', 'infinite_highest', 'infinite_honor'):
    payload['state'].pop(key, None)
with tempfile.TemporaryDirectory() as folder:
    path = Path(folder)/'old.json'
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    restored = GameState.load(tables, path)
    assert (restored.infinite_level, restored.infinite_highest,
            restored.infinite_honor) == (1, 1, 0)

# Real Tk host + original event shape.
event_file = data.root/'events'/'_infinite_arena_contract_test.json'
event_file.write_text(json.dumps([
    {'id': 1, 'type': 'openui', 'parameters': {'uiid': 20, 'par1': 1}},
    {'id': 2, 'type': 'closeui', 'parameters': {'no': 4, 'yes': 5}},
    {'id': 4, 'type': 'end'},
    {'id': 5, 'type': 'fight', 'parameters': {'type': 5, 'npcid': 1}},
    {'id': 6, 'type': 'fightover', 'parameters': {'win': 7, 'lose': 4}},
    {'id': 7, 'type': 'end'},
], ensure_ascii=False), encoding='utf-8')
root = tk.Tk()
root.withdraw()
try:
    app = NativeGame(root, data)
    app.runtime.file = ''
    app.display_request = None
    app.state.grant('700002', 3)
    app.runtime.start('_infinite_arena_contract_test.json')
    app.drive()
    root.update()
    assert app.ui_open and '无限竞技场' in app.ui_info.get()
    app.ui_actions['confirm_Button']()
    root.update()
    assert app.battle and app.battle.kind == 'infinite_arena'
    assert app.state.count('700002') == 2
    app.battle.result = 'win'
    app.finish_battle()
    root.update()
    assert app.state.infinite_level == 2
    assert app.state.infinite_honor == 1
    assert app.state.count('700007') == 1
finally:
    root.destroy()
    event_file.unlink(missing_ok=True)

report = {
    'levels': ['30', '60', '90', '120', '121'],
    'enemy_count': 6, 'entry_cost': ['700002', 1],
    'honor_reward': 1, 'level_after_win': 2,
    'loss_keeps_level': True, 'old_save_migration': True,
    'real_event_flow': True,
}
out = ROOT/'outputs/verification/infinite-arena.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(report)