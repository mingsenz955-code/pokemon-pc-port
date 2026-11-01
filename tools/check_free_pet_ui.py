"""Original FreePetConfirmUI for real pet release."""
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
    state = GameState(data.tables, seed=79)
    app = NativeGame(root, data)
    app.state = state
    assert len(state.pets) >= 2
    target = state.pets[1]
    app.open_free_pet(target.uid)
    assert app.ui_render_args['name'] == 'FreePetConfirmUI'
    assert 'confirm_Button' in app.ui_actions
    app.ui_actions['cancel_Button']()
    assert app.ui_render_args['name'] == 'PetListUI'
    assert target in state.pets
    app.close_ui()

    app.open_free_pet(target.uid)
    app.ui_actions['confirm_Button']()
    assert target not in state.pets
    assert app.ui_render_args['name'] == 'PetListUI'
    app.close_ui()

    app.open_free_pet(state.pets[state.active_pet].uid)
    app.ui_actions['confirm_Button']()
    assert app.ui_render_args['name'] == 'FreePetConfirmUI'
    assert '出战中' in app.ui_info.get()
    app.ui_actions['cancel_Button']()
    app.close_ui()

    sample = state.pets[0]
    app.open_pet_property(sample.uid)
    app.ui_actions['free_Button']()
    assert app.ui_render_args['name'] == 'FreePetConfirmUI'
    app.ui_actions['cancel_Button']()
    assert app.ui_render_args['name'] == 'PetPropertyUI'
    app.ui_actions['close_Button']()
    print('FreePetConfirmUI checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous