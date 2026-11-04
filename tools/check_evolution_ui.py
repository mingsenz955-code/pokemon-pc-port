"""Original EvolutionConditionUI with real level/material checks."""
import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from game_state import GameState, numbers  # noqa: E402
from original_data import OriginalData  # noqa: E402
from pc_game import NativeGame  # noqa: E402

saves = tempfile.TemporaryDirectory()
previous = os.environ.get('POCKET_NATIVE_SAVE_DIR')
os.environ['POCKET_NATIVE_SAVE_DIR'] = saves.name
root = tk.Tk()
root.withdraw()
try:
    data = OriginalData(ROOT/'original-1.20.4')
    state = GameState(data.tables, seed=103)
    app = NativeGame(root, data)
    app.state = state
    pet = state.pets[0]
    species, evolution = next(
        (key, row) for key, row in data.tables['Evolution'].items()
        if row['petId'] in data.tables['Pet'])
    pet.species = str(species)
    pet.level = max(int(evolution['level']), pet.level)
    for item_id, count in zip(numbers(evolution['itemIds']),
                              numbers(evolution['itemCounts'])):
        state.inventory[str(item_id)] = int(count)
    target = data.tables['Pet'][evolution['petId']]['name']
    app.open_evolution(pet.uid)
    assert app.ui_render_args['name'] == 'EvolutionConditionUI'
    assert target in app.ui_info.get()
    app.ui_actions['evolution_Button']()
    assert pet.species == evolution['petId']
    assert app.ui_render_args['name'] == 'PetListUI'
    app.close_ui()
    print('EvolutionConditionUI checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous