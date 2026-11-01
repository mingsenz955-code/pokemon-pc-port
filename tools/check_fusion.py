"""Original PetHeTi fusion rules and the real Tk UI button."""
import sys
import tkinter as tk
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from game_state import GameState
from pc_game import NativeGame
from event_runtime import Request


def two_parents(state, species_a='100028', species_b='100129'):
    a = state.add_generated_pet(species_a)
    b = state.add_generated_pet(species_b)
    if a not in state.bank:
        state.move_pet(a.uid, to_bank=True)
    if b not in state.bank:
        state.move_pet(b.uid, to_bank=True)
    return a, b


data = OriginalData(ROOT/'original-1.20.4')
state = GameState(data.tables, seed=123)
state.initialize(2)
a, b = two_parents(state)
a.variation, a.growth = [1, 2, 3, 4, 5], [6, 7, 8, 9, 10]
b.variation, b.growth = [3, 4, 5, 6, 7], [8, 9, 10, 11, 12]
state.grant('700002', 12)
state.grant('240018', 4)
child = state.fuse_pets(a.uid, b.uid)
assert child.species == '100034' and child.level == 1, child
assert child.variation == [2, 3, 4, 5, 6], child.variation
assert child.growth == [7, 8, 9, 10, 11], child.growth
assert state.count('700002') == 0 and state.count('240018') == 0
assert [p.species for p in state.bank] == ['100034']
assert a not in state.pets+state.bank and b not in state.pets+state.bank

# Reverse parent order is not a valid recipe for this ordered table entry.
a, b = two_parents(state)
state.grant('700002', 12)
state.grant('240018', 4)
before_bank = list(state.bank)
before_items = dict(state.inventory)
try:
    state.fuse_pets(b.uid, a.uid)
except ValueError as error:
    assert '配方' in str(error), error
else:
    raise AssertionError('reversed ordered fusion must not match')
assert state.bank == before_bank and state.inventory == before_items

# Insufficient materials must not remove either parent or any inventory.
a, b = two_parents(state)
state.inventory['700002'] = 0
state.inventory['240018'] = 0
before_bank = list(state.bank)
before_items = dict(state.inventory)
try:
    state.fuse_pets(a.uid, b.uid)
except ValueError as error:
    assert '材料' in str(error), error
else:
    raise AssertionError('fusion without materials must fail')
assert state.bank == before_bank and state.inventory == before_items

# Active party pets are rejected before any mutation.
active = state.pets[0]
try:
    state.fuse_pets(active.uid, active.uid)
except ValueError:
    pass
else:
    raise AssertionError('active pets must not fuse')

# The original Cocos heTi_Button is a real click target in the Tk host.
root = tk.Tk()
app = NativeGame(root, data)
app.runtime.sequence, app.runtime.file, app.runtime.pending = [], '', None
app.display_request, app.dialogue = None, None
aa = app.state.add_generated_pet('100028')
bb = app.state.add_generated_pet('100129')
app.state.grant('700002', 12)
app.state.grant('240018', 4)
app.open_ui(Request('openui', 'fusion-ui', 1, {'parameters': {'uiid': 34}}))
button = app.ui_buttons['Layer/root_Panel/heTi_Button']
app.on_ui_click(types.SimpleNamespace(x=(button[0]+button[2])/2, y=(button[1]+button[3])/2))
assert '合体成功' in app.ui_info.get(), app.ui_info.get()
assert [p.species for p in app.state.bank] == ['100034'], app.state.bank
# The same original layout also exposes a nested close button.
close = next(rect for name, rect in app.ui_buttons.items() if name.endswith('/close_Button'))
app.on_ui_click(types.SimpleNamespace(x=(close[0]+close[2])/2, y=(close[1]+close[3])/2))
assert not app.ui_open and app.ui_window is None
root.destroy()
print({'fusion_species': child.species, 'level': child.level,
       'variation': child.variation, 'growth': child.growth,
       'ordered_recipe': 'passed', 'ui_button': 'passed'})
import json
(ROOT/'outputs/verification/fusion.json').write_text(json.dumps({
    'fusion_species': child.species, 'level': child.level,
    'variation': child.variation, 'growth': child.growth,
    'ordered_recipe': True, 'ui_button': True,
}, ensure_ascii=False, indent=2), encoding='utf-8')