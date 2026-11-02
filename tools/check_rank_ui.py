"""RankUI must render original FightRank data, not the editor placeholder row."""
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
    app = NativeGame(root, data)
    app.state = GameState(data.tables, seed=26)
    app.state.add_preset(1)
    app.open_ui(Request('openui', 'rank', 1, {'parameters': {'uiid': 26}}))
    assert app.ui_base_layer.size == (800, 480)
    assert 'FightRank' in app.ui_info.get() and '50' in app.ui_info.get()
    first = data.tables['FightRank']['1']['name']
    assert '一个大鸭子' not in app.ui_info.get()
    assert first not in ('一个大鸭子', '5000')
    assert 'rank_row_0' in app.ui_actions and 'rank_row_9' in app.ui_actions
    app.ui_actions['rank_row_0']()
    assert first in app.ui_info.get()
    app.ui_actions['integralTag_Button']()
    assert 'PetCollectCountRank' in app.ui_info.get()
    app.ui_actions['taoFaTag_Button']()
    assert 'RankNpcPet' in app.ui_info.get()
    assert app.ui_base_layer.size == (800, 480)
    app.close_ui()
    print('RankUI checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous