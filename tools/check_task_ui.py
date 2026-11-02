"""TaskUI three original tabs: main/branch/daily rows, no remote task reward."""
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
state = GameState(data.tables, seed=21)
state.main_task, state.main_state = 129, 3
state.task_counts['main:129'] = [42]
state.branch_states['4101'] = 4
state.task_counts['branch:4101'] = [30]
root = tk.Tk()
root.withdraw()
try:
    app = NativeGame(root, data)
    app.runtime.sequence, app.runtime.file, app.runtime.pending = [], '', None
    app.state = state
    app.guide.rebind(state)
    app.open_ui(Request('openui', 'task-ui-check', 1,
                        {'parameters': {'uiid': 44}}))
    assert app.ui_open and app.ui_window is None
    page = app.task_page
    image = page.render()
    assert image.size == (800, 480)
    assert 'receive_Button' not in page.hits
    assert '42/300' in page.info()
    before = state.count('700001')
    app.ui_actions['receive_Button']()
    assert state.count('700001') == before and app.ui_open
    assert not app.guide.active
    app.ui_actions['tag_2_Button']()
    assert '石匠德罗的委托' in page.info()
    assert '30/30' in page.info()
    page.render()
    assert 'receive_Button' not in page.hits
    app.ui_actions['tag_3_Button']()
    page.render()
    assert any(row[1]['name'] == '全能训练' for row in page.rows)
    app.ui_actions['tag_1_Button']()
    assert '收集木料' in page.info()
    app.ui_actions['close_Button']()
    assert not app.ui_open and app.task_page is None
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()

print('TaskUI three-tab checks passed')
