"""Arena (竞技场) data, progression, event flow and real UI test.

This test deliberately runs the original event shape:

    openui 10 par1=1 -> closeui yes -> fight type=3 npcid=1
    win -> fightover win -> openui 10 par2=2 -> closeui yes -> fight ...

It proves a real arena Battle is constructed from ArenaNpc/ArenaNpcPet, that a
fresh entry consumes one 700002 badge, that a consecutive win is free, that a
loss resets the streak, and that rank/title/drop/UI text change accordingly.
"""
import json
import sys
import tempfile
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))

from arena import ArenaProgress, make_arena_battle  # noqa: E402
from game_state import GameState  # noqa: E402
from original_data import OriginalData  # noqa: E402
from pc_game import NativeGame  # noqa: E402

data = OriginalData(ROOT/'original-1.20.4')
tables = data.tables

# -- pure progression ---------------------------------------------------------
state = GameState(tables)
state.initialize(1)
state.grant('700002', 3)
progress = ArenaProgress(state)
assert progress.rank('1') == 101
assert progress.entry_cost('1') == ('700002', 1)
assert progress.next_npc('1')['keyId'] == '10100'
state.arena_ranks['1'] = 92
assert progress.next_npc('1')['keyId'] == '10091'
assert progress.next_npc('1')['isBoss'] == '1'
state.arena_ranks['1'] = 1
assert progress.next_npc('1')['keyId'] == '10001'

# -- battle construction -------------------------------------------------------
state.arena_ranks['1'] = 101
battle = make_arena_battle(tables, state.pets, '1', state.rng, rank=101)
assert battle.kind == 'arena'
assert len(battle.enemy) == 6
assert all(unit.pet.level == 30 for unit in battle.enemy)
assert not battle.can_escape and not battle.can_catch
assert battle.arena_npc_id == '10100'
assert all(unit.pet.species in tables['Pet'] for unit in battle.enemy)

# -- entry/win/title/drop ------------------------------------------------------
progress.enter('1')
assert state.count('700002') == 2
state.arena_ranks['1'] = 92
win = progress.finish('1', '10091', 'win')
assert progress.entry_cost('1') is None
assert win['rank_after'] == 91
assert state.arena_ranks['1'] == 91
assert state.arena_titles['1'] == 10091
assert progress.title_name('1') == '努力奋斗'
assert state.count('700001') >= 500
assert state.arena_streak['1'] == 1

# A free consecutive entry consumes no badge; a loss resets the streak.
progress.enter('1')
assert state.count('700002') == 2
progress.finish('1', '10090', 'lose')
assert state.arena_streak['1'] == 0
assert progress.entry_cost('1') == ('700002', 1)
assert state.count('700002') == 2

# Insufficient badge must not mutate state.
empty = GameState(tables)
empty.inventory.pop('700002', None)
try:
    ArenaProgress(empty).enter('1')
except ValueError as error:
    assert '不足' in str(error)
else:
    raise AssertionError('arena accepted a challenge without badges')
assert empty.count('700002') == 0

# -- old-save migration -------------------------------------------------------
old = GameState(tables)
old.initialize(1)
payload = old.payload()
for key in ('arena_ranks', 'arena_titles', 'arena_wins', 'arena_streak'):
    payload['state'].pop(key, None)
with tempfile.TemporaryDirectory() as folder:
    path = Path(folder)/'old.json'
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    restored = GameState.load(tables, path)
    assert restored.arena_ranks == {'1': 101, '2': 101}
    assert restored.arena_titles == {'1': 0, '2': 0}

# -- real UI and full original event flow ------------------------------------
event_file = data.root/'events'/'_arena_contract_test.json'
event_file.write_text(json.dumps([
    {'id': 1, 'type': 'openui', 'parameters': {'uiid': 10, 'par1': 1, 'par2': 1}},
    {'id': 2, 'type': 'closeui', 'parameters': {'no': 4, 'yes': 5}},
    {'id': 4, 'type': 'end'},
    {'id': 5, 'type': 'fight', 'parameters': {'type': 3, 'npcid': 1}},
    {'id': 6, 'type': 'fightover', 'parameters': {'win': 7, 'lose': 4}},
    {'id': 7, 'type': 'openui', 'parameters': {'uiid': 10, 'par1': 1, 'par2': 2}},
    {'id': 8, 'type': 'closeui', 'parameters': {'no': 4, 'yes': 5}},
], ensure_ascii=False), encoding='utf-8')
root = tk.Tk()
root.withdraw()
try:
    app = NativeGame(root, data)
    app.runtime.file = ''
    app.display_request = None
    app.state.grant('700002', 3)
    app.runtime.start('_arena_contract_test.json')
    app.drive()
    root.update()
    assert app.ui_open
    assert '奥林匹斯竞技场' in app.ui_info.get()
    assert '当前排名：101' in app.ui_info.get()
    app.ui_actions['challenge_Button']()
    root.update()
    assert app.battle and app.battle.kind == 'arena'
    assert not app.ui_open and app.state.count('700002') == 2
    assert app.battle.arena_npc_id == '10100'
    app.battle.result = 'win'
    app.finish_battle()
    root.update()
    assert app.ui_open and app.state.arena_ranks['1'] == 100
    assert app.state.arena_streak['1'] == 1
    assert '当前排名：100' in app.ui_info.get()
    assert '本场免费' in app.ui_info.get()
    app.ui_actions['challenge_Button']()
    root.update()
    assert app.battle and app.battle.kind == 'arena'
    assert app.state.count('700002') == 2
    app.battle.result = 'lose'
    app.finish_battle()
    root.update()
    assert not app.ui_open
    assert app.state.arena_streak['1'] == 0
    assert app.state.arena_ranks['1'] == 100
finally:
    root.destroy()
    event_file.unlink(missing_ok=True)

report = {
    'arena': '1', 'rank_start': 101, 'first_opponent': '10100',
    'boss_opponent': '10091', 'top_opponent': '10001',
    'enemy_count': 6, 'enemy_level': 30,
    'entry_cost': ['700002', 1], 'free_consecutive': True,
    'win_rank': 91, 'win_title': '努力奋斗',
    'loss_resets_streak': True, 'old_save_migration': True,
    'real_event_flow': True,
}
out = ROOT/'outputs/verification/arena.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(report)