"""Battle victory uses the original WorldMonsterBattleResultUI layer."""
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
    confirm = app.cocos_ui.rects['confirm_Button']
    assert ui.hits['result_continue'] == tuple(round(v) for v in confirm)
    # The original result plate replaces the old dark host-made panel.
    assert frame.getpixel((512, 150))[3] > 0
    print('Battle result UI checks passed')
finally:
    root.destroy()