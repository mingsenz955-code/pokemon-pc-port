"""The top-left save button must open the original SaveConfirmUI and write a user-local save."""
import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData  # noqa: E402
from pc_game import NativeGame  # noqa: E402


def click_rect(app, suffix):
    key, rect = next((key, rect) for key, rect in app.ui_buttons.items()
                     if key.endswith('/'+suffix))
    app.on_ui_click(SimpleNamespace(x=(rect[0]+rect[2])/2, y=(rect[1]+rect[3])/2))
    return key


saves = tempfile.TemporaryDirectory()
previous = os.environ.get('POCKET_NATIVE_SAVE_DIR')
os.environ['POCKET_NATIVE_SAVE_DIR'] = saves.name
root = tk.Tk()
root.withdraw()
try:
    app = NativeGame(root, OriginalData(ROOT/'original-1.20.4'))
    app.runtime.file, app.runtime.sequence, app.runtime.pending = '', [], None
    app.booting = False
    app.save_ui()
    root.update()
    assert app.ui_open and app.ui_window and app.ui_window.winfo_exists()
    assert app.ui_render_args['name'] == 'SaveConfirmUI'
    before = app.state.activities.get('save_total', 0)
    click_rect(app, 'confirm_Button')
    root.update()
    assert not app.ui_open
    assert app.save_path.exists(), app.save_path
    assert app.state.activities['save_total'] == before+1
    # Cancel must not write a second state change.
    app.save_ui()
    root.update()
    click_rect(app, 'cancel_Button')
    root.update()
    assert not app.ui_open
    assert app.state.activities['save_total'] == before+1
    print('Save UI checks passed:', app.save_path)
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous