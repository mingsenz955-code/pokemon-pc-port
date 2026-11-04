"""Normal victory uses outcome/calculation layers and advances on screen taps."""
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
    for unit in app.battle.enemy:
        unit.hp = 0
    app.battle._check_end()
    assert app.battle.result == 'win'
    ui.anim = None
    ui.anim_queue = []
    frame = ui.render()
    assert frame.size == (960, 576)
    assert 'result_continue' in ui.hits
    assert ui.hits['result_continue'] == (0, 0, 960, 576)
    for _ in range(20):
        action = ui.click(480, 288)
        if action == 'finish':
            break
        ui.render()
    assert action == 'finish'
    print('Battle result UI checks passed')
finally:
    root.destroy()