"""Wild-map encounter distance and real VillageEnemy battle wiring."""
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
    state = GameState(data.tables, seed=211)
    state.initialize(1)
    state.add_preset(1)
    state.starter_id = 1
    app = NativeGame(root, data)
    app.state = state
    app.load_map(201, 3*64+32, 3*64)
    app.runtime.file = None
    app.runtime.sequence = []
    app.runtime.index = 0
    app.runtime.pending = None
    app.dialogue = None
    app.display_request = None
    assert app.encounter_threshold > 0, 'wild map must arm encounter distance'
    assert 30 <= app.encounter_threshold <= 40
    app.encounter_distance = app.encounter_threshold*64
    assert app.check_encounter() is True
    assert app.battle is not None and app.battle.kind == 'wild'
    assert app.battle.enemy_active is not None
    print('Wild encounter checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous