"""Original GetItemUI: real reward title and item list."""
import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
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
    state = GameState(data.tables, seed=37)
    app = NativeGame(root, data)
    app.state = state
    app.show_reward('宝藏获得', [('230001', 2), ('700001', 100)])
    assert app.ui_open and app.ui_render_args['name'] == 'GetItemUI'
    assert '宝藏获得' in app.ui_info.get()
    assert 'confirm_Button' in app.ui_actions
    app.ui_actions['confirm_Button']()
    assert not app.ui_open
    print('GetItemUI checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous