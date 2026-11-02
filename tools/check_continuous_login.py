"""ContinuousLogin table rewards, cumulative missed-day progress, atomic claim and UI."""
import sys
import os
import tempfile
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))

from game_state import GameState  # noqa: E402
from original_data import OriginalData  # noqa: E402
from pc_game import NativeGame  # noqa: E402
from continuous_login import ContinuousLogin  # noqa: E402
from event_runtime import Request  # noqa: E402

saves = tempfile.TemporaryDirectory()
previous = os.environ.get('POCKET_NATIVE_SAVE_DIR')
os.environ['POCKET_NATIVE_SAVE_DIR'] = saves.name
data = OriginalData(ROOT/'original-1.20.4')
tables = data.tables
state = GameState(tables, seed=3)
state.inventory.clear()
login = ContinuousLogin(state)

status = login.status('2026-01-01')
assert status['next_day'] == 1 and not status['claimed_today']
result = login.claim('2026-01-01')
assert result['day'] == 1 and result['reward'] == '220006' and result['count'] == 1
assert state.count('220006') == 1
assert login.status('2026-01-01')['claimed_today']
try:
    login.claim('2026-01-01')
    raise AssertionError('claimed the same calendar day twice')
except ValueError:
    pass
assert state.count('220006') == 1

# Next day is day two: five badges.
assert login.status('2026-01-02')['next_day'] == 2
result = login.claim('2026-01-02')
assert result['day'] == 2 and result['reward'] == '700002' and result['count'] == 5
assert state.count('700002') == 5

# A missed day keeps accumulated rewards; the next claim is day three.
assert not login.status('2026-01-04')['reset']
result = login.claim('2026-01-04')
assert result['day'] == 3 and result['reward'] == '250002'
assert state.count('220006') == 1
assert not login.status('2026-01-02')['can_claim']
try:
    login.claim('2026-01-02')
    raise AssertionError('clock rollback claimed another reward')
except ValueError:
    pass

# All seven days complete; further claims are rejected without rewards.
state.activities['continuous_login'] = {'day': 7, 'last': '2026-01-05'}
assert login.status('2026-01-06')['complete']
try:
    login.claim('2026-01-06')
    raise AssertionError('claimed beyond day seven')
except ValueError:
    pass
assert state.activities['continuous_login']['day'] == 7

# Atomic failure keeps cumulative progress and inventory unchanged.
state.activities['continuous_login'] = {'day': 2, 'last': '2026-01-01'}
before = dict(state.inventory)
old = tables['ContinuousLogin']['3']
tables['ContinuousLogin']['3'] = {'rewardKid': 'not-a-real-item', 'rewardCount': '1'}
try:
    login.claim('2026-01-08')
    raise AssertionError('missing reward id was granted')
except KeyError:
    pass
finally:
    tables['ContinuousLogin']['3'] = old
assert state.inventory == before
assert state.activities['continuous_login'] == {'day': 2, 'last': '2026-01-01'}

# UI: claim through the original layout and close.
root = tk.Tk()
root.withdraw()
try:
    app = NativeGame(root, data)
    app.runtime.sequence, app.runtime.file, app.runtime.pending = [], '', None
    app.display_request = None
    app.state.activities.pop('continuous_login', None)
    app.state.inventory['220006'] = 0
    app.open_ui(Request('openui', 'login-check', 1,
                        {'parameters': {'uiid': 12}}))
    assert app.ui_open and 'get_Button' in app.ui_actions
    app.ui_actions['get_Button']()
    assert app.state.count('220006') == 1
    assert app.state.activities['continuous_login']['day'] == 1
    assert '领取成功' in app.ui_info.get()
    assert app.reward_visible
    app.ui_actions['confirm_Button']()
    app.ui_actions['close_Button']()
    assert not app.ui_open
finally:
    root.destroy()
    saves.cleanup()
    if previous is None:
        os.environ.pop('POCKET_NATIVE_SAVE_DIR', None)
    else:
        os.environ['POCKET_NATIVE_SAVE_DIR'] = previous

print('continuous login checks passed')
