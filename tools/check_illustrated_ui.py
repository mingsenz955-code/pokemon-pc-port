"""Original IllustratedUI: five PetKindEnum tabs and encyclopedia state."""
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
    state = GameState(data.tables, seed=31)
    first = next(k for k, row in data.tables['Pet'].items() if row.get('kind') == '1')
    state.encyclopedia = [first]
    app = NativeGame(root, data)
    app.state = state
    app.illustrated_ui()
    assert app.ui_open and app.ui_render_args['name'] == 'IllustratedUI'
    for kind in range(1, 6):
        assert f'tag_{kind}_Button' in app.ui_actions
    app.ui_actions['tag_3_Button']()
    assert '飞行系' in app.ui_info.get()
    app.ui_actions['tag_1_Button']()
    assert '植物系' in app.ui_info.get()
    assert '已收录' in app.ui_info.get() or '未收录' in app.ui_info.get()
    app.ui_actions['close_Button']()
    assert not app.ui_open
    print('IllustratedUI checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous