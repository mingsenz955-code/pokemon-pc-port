"""Achievement table: 142 rows, verified condition progress, atomic claims."""
import sys
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))

from achievements import Achievements  # noqa: E402
from event_runtime import Request  # noqa: E402
from game_state import GameState  # noqa: E402
from original_data import OriginalData  # noqa: E402
from pc_game import NativeGame  # noqa: E402

data = OriginalData(ROOT/'original-1.20.4')
state = GameState(data.tables, seed=41)
api = Achievements(state)
assert len(api.rows) == 142
assert api.status('4301') == 'progress'
assert api.status('1003') == 'unsupported'

# Map achievement 4301: reach map 308.
state.visited_maps.append(308)
assert api.progress('4301')[:2] == (1, 1)
assert api.status('4301') == 'ready'
result = api.claim('4301')
assert result['score'] == 10
assert state.count('240002') == 1
assert api.status('4301') == 'claimed'
assert api.score() == 10
try:
    api.claim('4301')
    raise AssertionError('duplicate achievement claim accepted')
except ValueError:
    pass

# Obstacle, talk, chest and branch conditions use real local counters.
state.removed_obstacles.append([202, 1, 2, 2])
state.activities['talk_total'] = 100
state.activities['village_chests'] = ['a']
state.completed_branch = [1]
assert api.progress('3401')[:2] == (1, 1)
assert api.progress('3402')[:2] == (1, 100)
assert api.progress('5501')[:2] == (100, 100)
assert api.progress('1801')[:2] == (1, 1)
assert api.progress('6001')[:2] == (1, 1)
assert api.claim('3401')['score'] == 5
assert state.count('210001') == 1

# Unsupported original condition types must not fabricate progress/rewards.
before = state.count('260017')
try:
    api.claim('1003')
    raise AssertionError('unsupported achievement claimed')
except ValueError as error:
    assert '不能伪造' in str(error)
assert state.count('260017') == before

# Original AchievementUI body lists all rows and exposes the claim action.
root = tk.Tk()
root.withdraw()
try:
    app = NativeGame(root, data)
    app.state = state
    app.open_ui(Request('openui', 'achievement-test', 1,
                        {'parameters': {'uiid': 45}}))
    assert app.ui_open
    assert '原版成就共 142 行' in app.ui_info.get()
    assert 'receive_Button' in app.ui_actions
    assert 'achievement_receive' in app.ui_actions
    app.ui_actions['close_Button']()
    assert not app.ui_open
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()

print('achievement checks passed')