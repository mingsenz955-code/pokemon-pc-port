"""Boot the native Tk host and render each newly interactive activity window."""
import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from pc_game import NativeGame
from event_runtime import Request

folder = ROOT/'outputs/verification/activity-ui'
folder.mkdir(parents=True, exist_ok=True)
if sys.platform == 'win32':
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
with tempfile.TemporaryDirectory() as saves:
    os.environ['POCKET_NATIVE_SAVE_DIR'] = saves
    root = tk.Tk()
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    app = NativeGame(root, OriginalData(ROOT/'original-1.20.4'))
    # Controlled UI fixture: no live story request is being acknowledged.
    app.runtime.sequence, app.runtime.file, app.runtime.pending = [], '', None
    app.display_request, app.dialogue = None, None
    app.state.initialize(1)
    app.state.add_preset(1)
    app.state.grant('220008', 2)
    app.state.grant('250006', 1)
    root.geometry('+0+0')
    def widgets(parent):
        for child in parent.winfo_children():
            yield child
            yield from widgets(child)
    for uiid in (4, 5, 6, 11, 17, 23, 29, 30):
        app.open_ui(Request('openui', 'ui-test', 1, {'parameters': {'uiid': uiid, 'par1': 601}}))
        win = app.ui_window
        win.geometry('+20+20')
        root.update()
        labels = [w.cget('text') for w in widgets(win) if isinstance(w, tk.Label)]
        assert not any('布局读取失败' in str(text) for text in labels), (uiid, labels)
        if uiid == 30:
            assert 'open_Button' in app.ui_actions
            app.ui_actions['open_Button']()
            root.update()
        assert not errors, errors
        area = (win.winfo_rootx(), win.winfo_rooty(),
                win.winfo_rootx()+win.winfo_width(), win.winfo_rooty()+win.winfo_height())
        ImageGrab.grab(bbox=area).save(folder/f'ui-{uiid}.png')
        app.close_transient_ui()
        print(f'Activity UI {uiid}: PASS')
    root.destroy()
