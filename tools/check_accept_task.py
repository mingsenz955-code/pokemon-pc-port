"""AcceptBTaskUI uses the original layout buttons and resumes the script once."""
import sys
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))

from event_runtime import Request  # noqa: E402
from game_state import GameState  # noqa: E402
from original_data import OriginalData  # noqa: E402
from pc_game import NativeGame  # noqa: E402

data = OriginalData(ROOT/'original-1.20.4')
state = GameState(data.tables, seed=31)
root = tk.Tk()
root.withdraw()
try:
    app = NativeGame(root, data)
    app.state = state
    request = Request('accepttask', 'pEvent8001901.json', 10,
                      {'parameters': {'btask': 14301, 'id': 10}})
    app.runtime.pending = request
    resumed = []
    app.runtime.resume = lambda result=None: resumed.append(result)
    app.drive = lambda: None
    app.accept_task_ui(request)
    assert app.accept_task_window is not None
    assert app.display_request is request
    assert 'accept_Button' in app.accept_task_buttons
    assert 'close_Button' in app.accept_task_buttons
    assert resumed == []
    app._accept_task_finish(True)
    assert resumed == [True]
    assert app.display_request is None
    assert app.accept_task_window is None
    assert not app.accept_task_window
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()

# A second independent window can be declined without accepting the task.
root = tk.Tk()
root.withdraw()
try:
    app = NativeGame(root, data)
    app.state = state
    request = Request('accepttask', 'pEvent8001901.json', 10,
                      {'parameters': {'btask': 14301, 'id': 10}})
    app.runtime.pending = request
    resumed = []
    app.runtime.resume = lambda result=None: resumed.append(result)
    app.drive = lambda: None
    app.accept_task_ui(request)
    app._accept_task_finish(False)
    assert resumed == [False]
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()

print('AcceptBTaskUI checks passed')