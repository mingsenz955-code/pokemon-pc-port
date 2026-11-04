"""Original SecondConfirmUI/TipConfirmUI wiring."""
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
    state = GameState(data.tables, seed=41)
    app = NativeGame(root, data)
    app.state = state
    app.open_ui(Request('openui', 'test-confirm', 1, {
        'parameters': {'uiid': 50, 'text': '要开始这场战斗吗？'}}))
    assert app.ui_open and app.ui_render_args['name'] == 'SecondConfirmUI'
    assert 'confirm_Button' in app.ui_actions and 'cancel_Button' in app.ui_actions
    assert '要开始' in app.ui_info.get()
    app.ui_actions['cancel_Button']()
    assert not app.ui_open
    app.about()
    assert app.ui_open and app.ui_render_args['name'] == 'TipConfirmUI'
    assert '尚未完成' in app.ui_info.get()
    app.ui_actions['confirm_Button']()
    assert not app.ui_open
    print('ConfirmUI checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous