"""Original BagUI tabs, item use and DebrisItem synthesis."""
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
    state = GameState(data.tables, seed=17)
    state.inventory = {'280010': 70, '700001': 100}
    app = NativeGame(root, data)
    app.state = state
    app.bag_ui()
    assert app.ui_open
    assert app.ui_render_args['name'] == 'BagUI'
    assert 'use_Button' in app.ui_actions
    assert 'heCheng_Button' in app.ui_actions
    for index in range(1, 6):
        assert f'tag_{index}_Button' in app.ui_actions
    app.ui_actions['tag_5_Button']()
    app.ui_actions['bag_synthesize']()
    assert state.count('280010') == 0
    assert any(pet.species == '100112' for pet in state.pets+state.bank)
    assert '合成成功' in app.ui_info.get()
    app.ui_actions['close_Button']()
    assert not app.ui_open
    print('BagUI checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous