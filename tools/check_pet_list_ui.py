"""Original PetListUI: party list, tabs, battle/evolve/use-item actions."""
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
    state = GameState(data.tables, seed=23)
    state.add_generated_pet('100110', 8)
    state.add_generated_pet('100111', 8)
    state.active_pet = 0
    app = NativeGame(root, data)
    app.state = state
    app.pets_ui()
    assert app.ui_open and app.ui_render_args['name'] == 'PetListUI'
    for key in ('joinBattle_Button', 'evolution_Button', 'useItem_Button', 'free_Button',
                'skill_Button', 'trainValue_Button'):
        assert key in app.ui_actions, key
    app.ui_actions['trainValue_Button']()
    app.ui_actions['trainValue_Button']()
    app.ui_actions['joinBattle_Button']()
    assert state.active_pet == 0
    # Selecting the second party member and joining really changes the lead
    # and reports it, instead of only repainting the same row.
    app.ui_actions['pet_row_1']()
    app.ui_actions['joinBattle_Button']()
    assert state.active_pet == 1
    assert '参战' in app.ui_info.get(), app.ui_info.get()
    # One free click only arms confirmation; it must not delete the active pet.
    before = len(state.pets)
    app.ui_actions['free_Button']()
    assert len(state.pets) == before
    app.ui_actions['confirm_Button']()
    # The current native rule permits releasing the active pet if another
    # living pet remains; only the last living battle pet is protected.
    assert len(state.pets) == before-1
    state.pets = [state.pets[0]]
    state.active_pet = 0
    app.open_free_pet(state.pets[0].uid)
    app.ui_actions['confirm_Button']()
    assert len(state.pets) == 1
    assert app.ui_info.get() == data.localized_text()['cantFreeLastPet']
    app.ui_actions['close_Button']()
    app.ui_actions['close_Button']()
    assert not app.ui_open
    print('PetListUI checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous
