"""Original PetPropertyUI with real stats/skills/talents and actions."""
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
    state = GameState(data.tables, seed=83)
    app = NativeGame(root, data)
    app.state = state
    pet = state.pets[0]
    app.open_pet_property(pet.uid)
    assert app.ui_render_args['name'] == 'PetPropertyUI'
    assert data.tables['Pet'][pet.species]['name'] in app.ui_info.get()
    for key in ('skillTag_Button', 'talentTag_Button', 'free_Button',
                'evolution_Button', 'close_Button'):
        assert key in app.ui_actions
    app.ui_actions['talentTag_Button']()
    talent_info = app.ui_info.get()
    app.ui_actions['skillTag_Button']()
    skill_info = app.ui_info.get()
    assert talent_info and skill_info
    app.ui_actions['close_Button']()
    assert not app.ui_open
    print('PetPropertyUI checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous