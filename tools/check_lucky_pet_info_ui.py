"""Original LuckyDrawPetInfoUI after a real lottery draw."""
import os
import sys
import tempfile
import time
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
    state = GameState(data.tables, seed=89)
    app = NativeGame(root, data)
    app.state = state
    state.functions['8'] = 1
    pet = state.pets[0]
    app.open_lucky_pet_info(pet.uid)
    assert app.ui_render_args['name'] == 'LuckyDrawPetInfoUI'
    for key in ('confirm_Button', 'weixin_Button', 'close_Button'):
        assert key in app.ui_actions
    assert data.tables['Pet'][pet.species]['name'] in app.ui_info.get()
    app.ui_actions['confirm_Button']()
    assert not app.ui_open

    app.open_lucky_pet_info(pet.uid, back='lottery')
    app.ui_actions['confirm_Button']()
    assert app.ui_open
    assert app.ui_window.title() == '抽宠'
    app.close_ui()
    print('LuckyDrawPetInfoUI checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous