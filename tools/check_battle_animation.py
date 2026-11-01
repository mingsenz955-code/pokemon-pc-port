"""Battle presentation timeline contract.

The combat rules emit events; BattleUI must turn them into visible feedback
without changing damage/HP results.  This is deliberately a bounded visual
test: it does not claim the original Spine timeline itself is reproduced.
"""
import json
import sys
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))

from original_data import OriginalData  # noqa: E402
from pc_game import NativeGame  # noqa: E402

data = OriginalData(ROOT/'original-1.20.4')
root = tk.Tk()
root.withdraw()
try:
    app = NativeGame(root, data)
    app.runtime.file = ''
    app.display_request = None
    app.start_battle('511051')
    ui = app.battle_ui
    before_hp = [unit.hp for unit in app.battle.enemy]
    ui._action('attack_Button')
    assert ui.anim is not None
    assert ui.anim['amount'] > 0
    assert ui.anim['side'] in ('player', 'enemy')
    frame0 = ui.render().copy()
    ui.advance(8)
    assert ui.anim['age'] == 8
    frame1 = ui.render()
    changed = sum(1 for x in range(620, 900, 4) for y in range(160, 400, 4)
                  if frame0.getpixel((x, y)) != frame1.getpixel((x, y)))
    assert changed > 100
    assert [unit.hp for unit in app.battle.enemy] != before_hp
    # The timeline must expire and stop forcing redraws.
    ui.advance(40)
    assert ui.anim is None
    assert ui.render().size == (1024, 576)
finally:
    root.destroy()

report = {'damage_event_animation': True, 'damage_float': True,
          'changed_pixels': changed, 'timeline_expires': True}
out = ROOT/'outputs/verification/battle-animation.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(report)