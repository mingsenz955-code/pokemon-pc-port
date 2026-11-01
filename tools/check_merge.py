"""Original PetMerge rules and the real merge UI buttons."""
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


def pet(state, species='100028', level=10, quality=1):
    p = state.add_generated_pet(species, level)
    p.quality = quality
    return p


data = OriginalData(ROOT/'original-1.20.4')
state = GameState(data.tables, seed=7)
state.initialize(2)
base = pet(state, level=10, quality=1)
material = pet(state, level=10, quality=1)
base_variation = list(base.variation)
base_growth = list(base.growth)
state.grant('700002', 2)
merged = state.merge_pets(base.uid, [material.uid])
assert merged is base
assert all(abs(a-b-.5) < 1e-6 for a, b in zip(merged.variation, base_variation)), merged.variation
assert all(abs(a-b-.5) < 1e-6 for a, b in zip(merged.growth, base_growth)), merged.growth
assert state.count('700002') == 0
assert [p.uid for p in state.bank] == [base.uid]

# Wrong material level/quality and insufficient currency are atomic failures.
base2 = pet(state, level=10, quality=1)
bad = pet(state, level=9, quality=1)
state.grant('700002', 2)
before_bank, before_items = list(state.bank), dict(state.inventory)
try:
    state.merge_pets(base2.uid, [bad.uid])
except ValueError as error:
    assert '等级' in str(error) or '材料' in str(error), error
else:
    raise AssertionError('low-level merge material must fail')
assert state.bank == before_bank and state.inventory == before_items

# UI: add_Button chooses the base, autoAdd_Button fills the material slot,
# merge_Button runs the original action.
root = tk.Tk()
app = NativeGame(root, data)
app.runtime.sequence, app.runtime.file, app.runtime.pending = [], '', None
app.display_request, app.dialogue = None, None
for level, quality in ((10, 1), (10, 1)):
    p = app.state.add_generated_pet('100028', level)
    p.quality = quality
app.state.grant('700002', 2)
app.open_ui(Request('openui', 'merge-ui', 1, {'parameters': {'uiid': 18}}))
app.ui_actions['add_Button']()
app.ui_actions['autoAdd_Button']()
app.ui_actions['merge_Button']()
assert '融合成功' in app.ui_info.get(), app.ui_info.get()
assert len(app.state.bank) == 1 and app.state.count('700002') == 0
app.close_ui()
root.destroy()
print({'merge_quality': merged.quality, 'variation': merged.variation,
       'growth': merged.growth, 'ui_button': 'passed'})
import json
(ROOT/'outputs/verification/merge.json').write_text(json.dumps({
    'merge_quality': merged.quality, 'variation': merged.variation,
    'growth': merged.growth, 'ui_button': True,
}, ensure_ascii=False, indent=2), encoding='utf-8')