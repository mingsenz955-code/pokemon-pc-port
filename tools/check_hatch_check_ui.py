"""Original HatchCheckUI with real take/hatch actions."""
import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from activities import Activities  # noqa: E402
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
    state = GameState(data.tables, seed=107)
    app = NativeGame(root, data)
    app.state = state
    item = next(iter(data.tables['HatchItem']))
    row = data.tables['HatchItem'][item]
    state.inventory[item] = 1
    activity = Activities(state)
    activity.put_egg(0, item)
    egg = state.activities['eggs']['0']
    egg['exp'] = int(row['exp'])
    for material, count in zip(numbers(row['itemIds']), numbers(row['itemCounts'])):
        state.inventory[str(material)] = int(count)
    app.open_hatch_check(0)
    assert app.ui_render_args['name'] == 'HatchCheckUI'
    assert '孵化经验' in app.ui_info.get()
    assert 'hatch_Button' in app.ui_actions
    app.ui_actions['hatch_Button']()
    assert egg['pet'] is not None
    assert app.ui_render_args['name'] == 'HatchRoomUI'
    app.open_hatch_check(0)
    app.ui_actions['takeBackEgg_Button']()
    assert '0' not in state.activities.get('eggs', {})
    assert app.ui_render_args['name'] == 'HatchRoomUI'
    app.close_ui()
    print('HatchCheckUI checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous