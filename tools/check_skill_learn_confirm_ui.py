"""Original SkillLearnConfirmUI before spending money/scrolls."""
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
    state = GameState(data.tables, seed=101)
    app = NativeGame(root, data)
    app.state = state
    pet = state.pets[0]
    pet.species = '101153'
    pet.skills = []
    keys = [str(k) for k in numbers(data.tables['Pet'][pet.species]['skillIds'])]
    key = next(k for k in keys if k not in pet.skills)
    row = data.tables['Skill'][key]
    state.inventory[row['moneyId']] = 999999
    app.open_skill_learn_confirm(pet.uid, key, back=6)
    assert app.ui_render_args['name'] == 'SkillLearnConfirmUI'
    assert 'confirm_Button' in app.ui_actions
    assert data.tables['Skill'][key]['name'] in app.ui_info.get()
    assert key not in pet.skills
    app.ui_actions['confirm_Button']()
    assert key in pet.skills
    assert app.ui_render_args['name'] == 'SkillLearnUI'
    app.close_ui()
    print('SkillLearnConfirmUI checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous