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
assert api.status('2701') == 'unsupported'

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

# Action counters feed the additional original condition types without guesses.
state.activities['caught_total'] = 1
state.activities['hatch_total'] = 3
state.activities['evolve_total'] = 10
state.activities['ride_total'] = 20
state.activities['save_total'] = 5
state.activities['play_seconds'] = 600*60
assert api.progress('201')[:2] == (1, 1)
assert api.progress('7301')[:2] == (3, 3)
assert api.progress('6601')[:2] == (10, 10)
assert api.progress('6301')[:2] == (20, 20)
assert api.progress('5901')[:2] == (5, 5)
assert api.progress('3102')[:2] == (600, 600)
assert api.claim('201')['score'] == 5
assert state.count('230001') >= 1
assert api.claim('7301')['score'] == 10
assert api.claim('6601')['score'] == 10
assert api.claim('6301')['score'] == 5
assert api.claim('5901')['score'] == 5
assert api.claim('3102')['score'] == 15

# Collection families and total battle wins use exact local party/bank data.
from types import SimpleNamespace  # noqa: E402
state.pets.extend(SimpleNamespace(quality=2) for _ in range(5))
state.activities['battle_wins'] = 1
assert api.progress('401')[:2] == (5, 5)
assert api.progress('2301')[:2] == (1, 1)
assert api.progress('101') is None
assert api.claim('401')['score'] == 5
assert api.claim('2301')['score'] == 5

# Item-type collections and recorded species/kinds use the original tables.
state.inventory = {key: 1 for key, row in data.tables['Item'].items()
                   if row.get('type') == '4'}
state.encyclopedia = [key for key, row in data.tables['Pet'].items()
                      if row.get('kind') == '5'][:5]
assert api.progress('1901')[0] >= 13
assert api.progress('1001')[:2] == (5, 5)
assert api.claim('1901')['score'] == 20
assert api.claim('1001')['score'] == 5

# Item-use counters come from GameState.use_item, not from invented progress.
state.activities['heal_items'] = {'230001': 20}
assert api.progress('6402')[:2] == (20, 20)
assert api.claim('6402')['score'] == 5
# The same counter is incremented by a real recovery item use.
state.pets[0].hp = 1
state.inventory['230001'] = 1
state.use_item('230001', state.pets[0])
assert state.activities['heal_items']['230001'] == 21

state.activities['shop_spent'] = {'700001': 10000}
assert api.progress('7001')[:2] == (10000, 10000)
assert api.claim('7001')['score'] == 10
state.activities['shop_talks'] = {'1': 100}
assert api.progress('5601')[:2] == (100, 100)
assert api.claim('5601')['score'] == 10

# Unsupported original condition types must not fabricate progress/rewards.
before = state.count('260017')
try:
    api.claim('2701')
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