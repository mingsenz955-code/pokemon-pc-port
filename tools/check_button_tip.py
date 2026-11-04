"""Original tutorial button hints must wait for the highlighted MainUI button."""
import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

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
    state = GameState(data.tables, seed=233)
    state.initialize(1)
    state.add_preset(1)
    app = NativeGame(root, data)
    app.state = state
    app.load_map(5801, 19*64+32, 20*64)
    app.make_frame()
    request = Request('button', 'pEvent101002.json', 27, {
        'text': '提示：点击一下这里，可以将界面按钮隐藏！',
        'nodekey': 'uiDisappear_Button'})
    app.display_request = request
    app.runtime.pending = request
    app.runtime.file = 'pEvent101002.json'
    app.runtime.sequence = []
    app.runtime.index = 0
    assert 'uiDisappear_Button' in app.scene_ui.hits
    rect = app.scene_ui.hits['uiDisappear_Button']
    # Empty ground must not dismiss the hint.
    app.on_click(SimpleNamespace(x=1, y=1))
    assert app.display_request is request
    app.on_click(SimpleNamespace(x=(rect[0]+rect[2])/2, y=(rect[1]+rect[3])/2))
    assert app.display_request is None
    assert app.scene_ui.hidden is True
    print('Button tip checks passed')
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous