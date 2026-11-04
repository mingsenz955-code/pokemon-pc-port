"""Original SkillReplaceUI: choose a slot and replace with a real scroll cost."""
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
    state = GameState(data.tables, seed=67)
    app = NativeGame(root, data)
    app.state = state
    pet = state.pets[0]
    pet.species = '101153'
    candidates = [str(key) for key in numbers(data.tables['Pet'][pet.species]['skillIds'])]
    pet.skills = candidates[:4]
    new_key = candidates[4]
    scroll = None
    skill_row = data.tables['Skill'][new_key]
    state.inventory[skill_row['moneyId']] = 999999
    app.open_skill_replace(pet.uid, new_key, scroll=scroll)
    assert app.ui_render_args['name'] == 'SkillReplaceUI'
    assert 'confirm_Button' in app.ui_actions
    assert app.ui_info.get()
    app.ui_actions['confirm_Button']()
    assert pet.skills[0] == new_key
    assert state.count(skill_row['moneyId']) == 999999-int(skill_row['moneyCount'])
    assert not app.ui_open
    print('SkillReplaceUI checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous