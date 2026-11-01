"""Original OpenChestConfirmUI + ChestItem 210001 real key consumption."""
import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from event_runtime import Request  # noqa: E402
from game_state import GameState  # noqa: E402
from original_data import OriginalData  # noqa: E402
from pc_game import NativeGame  # noqa: E402

saves = tempfile.TemporaryDirectory()
previous = os.environ.get('POCKET_NATIVE_SAVE_DIR')
os.environ['POCKET_NATIVE_SAVE_DIR'] = saves.name
root = tk.Tk()
root.withdraw()
try:
    data = OriginalData(ROOT/'original-1.20.4')
    state = GameState(data.tables, seed=73)
    app = NativeGame(root, data)
    app.state = state
    state.inventory['210001'] = 1
    state.inventory['240001'] = 3
    app.open_ui(Request('openui', 'chest', 1, {'parameters': {'uiid': 55}}))
    assert app.ui_render_args['name'] == 'OpenChestConfirmUI'
    assert app.ui_actions.get('confirm_Button')
    app.ui_actions['confirm_Button']()
    assert state.count('210001') == 0
    assert state.count('240001') == 2
    assert app.ui_render_args['name'] == 'GetItemUI'
    assert app.ui_info.get()
    app.ui_actions['confirm_Button']()
    assert not app.ui_open
    print('OpenChestConfirmUI checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous