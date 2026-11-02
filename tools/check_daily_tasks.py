"""DailyTask table, daily reset, claim/atomic rewards, hooks and TaskUI."""
import sys
import json
import tempfile
import tkinter as tk
from pathlib import Path
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
if sys.platform == 'win32':
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)

from activities import Activities  # noqa: E402
from daily_tasks import DailyTasks  # noqa: E402
from event_runtime import Request  # noqa: E402
from game_state import GameState  # noqa: E402
from original_data import OriginalData  # noqa: E402
from pc_game import NativeGame  # noqa: E402

# The table has seven normal tasks and one meta task.
data = OriginalData(ROOT/'original-1.20.4')
tables = data.tables
assert len(tables['DailyTask']) == 8
state = GameState(tables, seed=7)
state.inventory.clear()
daily = DailyTasks(state)
day = '2026-01-01'
status = daily.status(day)
assert [row['id'] for row in status] == [str(i) for i in range(1, 9)]
assert all(row['progress'] == 0 and not row['ready'] and not row['claimed']
           for row in status)
assert [row['required'] for row in status] == [7, 3, 1, 10, 1, 1, 3, 3]
assert daily.required('1') == 7 and daily.required('4') == 10

# Invalid claims do not modify anything.
for task_id in ('1', '2', '3', '8'):
    try:
        daily.claim(task_id, day)
        raise AssertionError('claimed an incomplete daily task')
    except ValueError:
        pass
assert not any(daily.claimed(str(i), day) for i in range(1, 9))

# Each action maps to its original condition type; progress caps at required.
checks = [
    ('catch', '3', 1), ('fight', '2', 3), ('talk', '4', 10),
    ('purchase', '8', 3), ('roulette', '5', 1), ('cards_win', '6', 1),
    ('running_win', '7', 3),
]
for action, task_id, count in checks:
    result = daily.record(action, count+5, day)
    assert result['task_id'] == task_id
    assert daily.counter(task_id, day) == count
    assert daily.counter(task_id, day) <= daily.required(task_id)
assert daily.normal_completed(day) == 7
assert daily.progress('1', day) == 0 and not daily.ready('1', day)
assert daily.record('catch', 1, day)['count'] == 1
assert daily.record('unknown', 1, day) is None

# Claim each row and check the exact original reward vector.
expected = {
    '1': {'240015': 5, '240018': 1, '280012': 3},
    '2': {'700001': 1000},
    '3': {'700008': 2000},
    '4': {'220002': 1},
    '5': {'220008': 1},
    '6': {'230014': 1},
    '7': {'220009': 1},
    '8': {'220005': 1},
}
for task_id in [str(i) for i in range(2, 9)]:
    result = daily.claim(task_id, day)
    assert result['task_id'] == task_id
    for item_id, count in expected[task_id].items():
        assert state.count(item_id) == count, (task_id, item_id)
    try:
        daily.claim(task_id, day)
        raise AssertionError('duplicate daily claim accepted')
    except ValueError:
        pass
    assert daily.progress('1', day) == int(task_id)-1
assert daily.ready('1', day) and daily.claim('1', day)['task_id'] == '1'
for item_id, count in expected['1'].items():
    assert state.count(item_id) == count

# The next local day clears counters and claims.  The old day's rewards stay.
status = daily.status('2026-01-02')
assert all(row['progress'] == 0 and not row['claimed'] for row in status)
assert state.count('240015') == 5
assert daily.record('catch', 1, '2026-01-02')['count'] == 1
assert daily.status('2026-01-02')[2]['progress'] == 1
assert daily.status('2026-01-01')[2]['progress'] == 1
assert daily.refresh('2026-01-01')['date'] == '2026-01-02'

# Saves persist the daily activity dictionary, including claimed ids.
with tempfile.TemporaryDirectory() as folder:
    path = Path(folder)/'daily.json'
    state.save(path)
    loaded = GameState.load(tables, path)
    saved = DailyTasks(loaded).status('2026-01-02')
    assert saved[2]['progress'] == 1
    assert not saved[0]['claimed']
    assert loaded.count('240015') == 5

# Shop purchase hook (three items counts as three, once per successful buy).
state2 = GameState(tables, seed=8)
state2.inventory.clear()
state2.inventory['700001'] = 10000
state2.buy('Shop', '114', 3)
assert state2.count('240001') == 3
assert DailyTasks(state2).counter('8') == 3
assert DailyTasks(state2).ready('8')

# Roulette hook consumes the original ticket and records the task.
state2.inventory['220009'] = 1
Activities(state2).spin_roulette()
assert DailyTasks(state2).counter('5') == 1

# A failed reward delivery rolls back both the partial inventory write and claim.
from unittest.mock import patch
failed_state = GameState(tables, seed=10)
failed_daily = DailyTasks(failed_state)
failed_daily.record('fight', 3, day)
before_money = failed_state.count('700001')
before_activity = json.dumps(failed_state.activities, sort_keys=True)
grant = failed_state.grant
def partial_failure(item_id, count):
    grant(item_id, count)
    raise ValueError('injected reward delivery failure')
with patch.object(failed_state, 'grant', side_effect=partial_failure):
    try:
        failed_daily.claim('2', day)
        raise AssertionError('failed reward delivery unexpectedly succeeded')
    except ValueError:
        pass
assert failed_state.count('700001') == before_money
assert json.dumps(failed_state.activities, sort_keys=True) == before_activity
assert not failed_daily.claimed('2', day)

if '--logic-only' in sys.argv:
    print('daily task logic checks passed; host and UI checks not run')
    sys.exit(0)

# Talk hook: a real original-format talk step is counted once when displayed.
state3 = GameState(tables, seed=9)
talk_file = ROOT/'original-1.20.4/events/_daily_talk_test.json'
talk_file.write_text(json.dumps([{'id': 1, 'type': 'talk',
                                  'text': '路人:今天也要完成每日任务。'}],
                                ensure_ascii=False), encoding='utf-8')
root_talk = tk.Tk()
root_talk.withdraw()
try:
    app_talk = NativeGame(root_talk, data)
    app_talk.state = state3
    app_talk.runtime.file, app_talk.runtime.sequence = '', []
    app_talk.runtime.pending, app_talk.runtime.queue = None, []
    app_talk.runtime.index = 0
    app_talk.display_request, app_talk.dialogue = None, None
    app_talk.runtime.start('_daily_talk_test.json')
    app_talk.drive()
    assert app_talk.dialogue == '路人:今天也要完成每日任务。'
    assert DailyTasks(state3).counter('4') == 1
finally:
    for job in root_talk.tk.call('after', 'info'):
        root_talk.after_cancel(job)
    root_talk.destroy()
    talk_file.unlink(missing_ok=True)

# TaskUI: all seven normal tasks are complete before opening, so the meta row
# is ready.  The default selection is row 1 and receive_Button claims it.
state2.inventory.clear()
state2.activities.pop('daily_tasks', None)
for action in ('catch', 'fight', 'talk', 'purchase', 'roulette',
               'cards_win', 'running_win'):
    DailyTasks(state2).record(action, DailyTasks(state2).required(
        DailyTasks.ACTIONS[action]))
for task_id in DailyTasks.NORMAL_IDS:
    DailyTasks(state2).claim(task_id)
root = tk.Tk()
try:
    app = NativeGame(root, data)
    app.runtime.sequence, app.runtime.file, app.runtime.pending = [], '', None
    app.state = state2
    app.open_ui(Request('openui', 'daily-check', 1,
                        {'parameters': {'uiid': 44, 'page': 'daily'}}))
    assert app.ui_open
    win = app.ui_window
    win.geometry('+20+20')
    win.lift()
    win.attributes('-topmost', True)
    root.update()
    area = (win.winfo_rootx(), win.winfo_rooty(),
            win.winfo_rootx()+win.winfo_width(), win.winfo_rooty()+win.winfo_height())
    shot = ROOT/'outputs/verification/daily-tasks.png'
    shot.parent.mkdir(parents=True, exist_ok=True)
    ImageGrab.grab(bbox=area).save(shot)
    assert 'receive_Button' in app.ui_actions
    assert 'tag_1_Button' in app.ui_actions
    assert 'tag_2_Button' in app.ui_actions
    assert 'tag_3_Button' in app.ui_actions
    assert '全能训练' in app.ui_info.get()
    daily_text = app.ui_info.get()
    app.ui_actions['tag_1_Button']()
    assert app.ui_info.get() != daily_text
    gold_before = app.state.count('700001')
    app.ui_actions['receive_Button']()
    assert app.state.count('700001') == gold_before
    assert '不会伪造' in app.ui_info.get()
    app.ui_actions['tag_2_Button']()
    assert '支线' not in app.ui_info.get() or '当前页' in app.ui_info.get()
    app.ui_actions['tag_3_Button']()
    assert '全能训练' in app.ui_info.get()
    app.ui_actions['receive_Button']()
    assert '领取成功' in app.ui_info.get()
    assert app.state.count('240015') == 5 and app.state.count('240018') == 1
    app.ui_actions['close_Button']()
    assert not app.ui_open
finally:
    root.destroy()

print('daily task checks passed')
