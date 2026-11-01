"""Budokan (道馆试练) data, twenty-step progression and real event flow.

The original trial-tower UI is only a gate.  For ``fight type=4`` the event's
``npcid`` is the Budokan id; the concrete opponent must come from the ordered
``BudokanNpc`` list and its ``BudokanNpcPet`` rows.
"""
import json
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))

from budokan import BudokanProgress, make_budokan_battle  # noqa: E402
from game_state import GameState  # noqa: E402
from original_data import OriginalData  # noqa: E402
from pc_game import NativeGame  # noqa: E402

if sys.platform == 'win32':
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)

data = OriginalData(ROOT/'original-1.20.4')
tables = data.tables
state = GameState(tables)
state.initialize(1)
state.pets = [state.preset_pet('1')]
state.inventory.clear()
progress = BudokanProgress(state)

assert progress.gym('1')['name'] == '深蓝道馆'
assert progress.total('1') == 20
assert progress.wins('1') == 0
assert progress.next_npc('1')['keyId'] == '101'
assert progress.next_npc('1')['name'] == '卡尔普'
assert progress.opponents('1')[-1]['keyId'] == '120'
for gym_id, first, last in [('1', '101', '120'), ('2', '201', '220'),
                            ('3', '301', '320'), ('4', '401', '420'),
                            ('5', '501', '520')]:
    assert progress.total(gym_id) == 20
    assert progress.opponents(gym_id)[0]['keyId'] == first
    assert progress.opponents(gym_id)[-1]['keyId'] == last

battle = make_budokan_battle(tables, state.pets, '1', '101', state.rng)
battle.player[0].participated = True
assert battle.kind == 'budokan'
assert len(battle.enemy) == 3
assert all(unit.pet.species in tables['Pet'] for unit in battle.enemy)
assert not battle.can_catch and not battle.can_escape
assert battle.budokan_id == '1' and battle.budokan_npc_id == '101'

# A real victory uses the normal Battle reward transaction (dropPros was
# synthesized from the BudokanNpc row), then advances exactly one step.
battle.result = 'win'
battle._award()
battle.apply_rewards(state)
assert battle.drops == [('700001', 100)]
assert state.count('700001') == 100
summary = progress.finish('1', '101', 'win')
assert summary['before'] == 0 and summary['after'] == 1
assert progress.next_npc('1')['keyId'] == '102'

# A loss never advances.
loss = progress.finish('1', '102', 'lose')
assert loss['after'] == 1
assert progress.wins('1') == 1

# Duplicate/false opponents are rejected rather than silently advancing.
try:
    progress.finish('1', '103', 'win')
    raise AssertionError('accepted an out-of-order gym opponent')
except ValueError:
    pass

# Walk all twenty rows to verify the final configured material is granted once.
for npc in progress.opponents('1')[1:]:
    spec = make_budokan_battle(tables, state.pets, '1', npc['keyId'], state.rng)
    spec.player[0].participated = True
    spec.result = 'win'
    spec._award()
    spec.apply_rewards(state)
    progress.finish('1', npc['keyId'], 'win')
assert progress.complete('1')
assert progress.next_npc('1') is None
assert state.count('240011') == 1
assert state.count('700001') == 2400
try:
    progress.finish('1', '120', 'win')
    raise AssertionError('granted a 21st gym victory')
except ValueError:
    pass
assert progress.wins('1') == 20
assert state.count('240011') == 1

# Progress survives the normal save/load path.
with tempfile.TemporaryDirectory() as folder:
    path = Path(folder)/'budokan.json'
    state.save(path)
    restored = GameState.load(tables, path)
    assert BudokanProgress(restored).wins('1') == 20
    assert BudokanProgress(restored).complete('1')

# -- real UI and the original openui 15 -> closeui yes -> fight type=4 flow ---
event_file = data.root/'events'/'_budokan_contract_test.json'
event_file.write_text(json.dumps([
    {'id': 1, 'type': 'openui', 'parameters': {'uiid': 15, 'par1': 1}},
    {'id': 2, 'type': 'closeui', 'parameters': {'no': 4, 'yes': 5}},
    {'id': 3, 'type': 'end'},
    {'id': 4, 'type': 'end'},
    {'id': 5, 'type': 'fight', 'parameters': {'type': 4, 'npcid': 1}},
    {'id': 6, 'type': 'fightover', 'parameters': {'win': 8, 'lose': 7}},
    {'id': 7, 'type': 'end'},
    {'id': 8, 'type': 'openui', 'parameters': {'uiid': 15, 'par1': 1}},
    {'id': 9, 'type': 'closeui', 'parameters': {'no': 10, 'yes': 5}},
    {'id': 10, 'type': 'end'},
], ensure_ascii=False), encoding='utf-8')
root = tk.Tk()
try:
    app = NativeGame(root, data)
    app.runtime.file = ''
    app.display_request = None
    app.state.pets = [app.state.preset_pet('1')]
    app.state.budokans['1'] = 0
    app.state.grant('240011', 0)
    app.runtime.start('_budokan_contract_test.json')
    app.drive()
    root.update()
    assert app.ui_open
    assert '深蓝道馆' in app.ui_info.get()
    assert '0 / 20' in app.ui_info.get()
    assert '卡尔普' in app.ui_info.get()
    win = app.ui_window
    win.geometry('+20+20')
    win.lift()
    win.attributes('-topmost', True)
    root.update()
    area = (win.winfo_rootx(), win.winfo_rooty(),
            win.winfo_rootx()+win.winfo_width(), win.winfo_rooty()+win.winfo_height())
    shot = ROOT/'outputs/verification/budokan-gym.png'
    shot.parent.mkdir(parents=True, exist_ok=True)
    ImageGrab.grab(bbox=area).save(shot)
    app.ui_actions['confirm_Button']()
    root.update()
    assert app.battle and app.battle.kind == 'budokan'
    assert app.battle.budokan_npc_id == '101'
    assert not app.ui_open
    app.battle.player[0].participated = True
    app.battle.result = 'win'
    app.battle._award()
    app.finish_battle()
    root.update()
    assert app.ui_open
    assert app.state.budokans['1'] == 1
    assert '1 / 20' in app.ui_info.get()
    assert '下一位：克鲁申' in app.ui_info.get()
    app.ui_actions['close_Button']()
    assert not app.ui_open
finally:
    root.destroy()
    event_file.unlink(missing_ok=True)

print('budokan checks passed')