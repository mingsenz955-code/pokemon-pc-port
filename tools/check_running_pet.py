"""Original RunningPet formula, bet wrap, settlement, UI contract and save."""
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))

from game_state import GameState  # noqa: E402
from original_data import OriginalData  # noqa: E402
from pc_game import NativeGame  # noqa: E402
from running_pet import RunningPetGame  # noqa: E402
from event_runtime import Request  # noqa: E402

data = OriginalData(ROOT/'original-1.20.4')
tables = data.tables

# Formula_GetRunningPetWinProbability is exactly 1/(1.2 + override/3).
for override, expected in [(1.5, 1/1.7), (4.5, 1/2.7), (10.0, 1/(1.2+10/3))]:
    assert abs(RunningPetGame.win_probability(override)-expected) < 1e-12

# A deterministic session: four runners, selected #1 at 4.5x, 100 medal bet.
class FakeRng:
    def __init__(self, ints=(), ranges=(), uniforms=()):
        self.ints, self.ranges, self.uniforms = list(ints), list(ranges), list(uniforms)
    def randint(self, low, high):
        value = self.ints.pop(0)
        assert low <= value <= high, (low, high, value)
        return value
    def randrange(self, stop):
        return self.ranges.pop(0)
    def random(self):
        return 0.5
    def uniform(self, low, high):
        value = self.uniforms.pop(0)
        assert low <= value <= high, (low, high, value)
        return value

def make_session(bet=100, selected=0):
    return {
        'contenders': [
            {'index': 0, 'id': '1', 'name': '小火龙', 'filePath': 'zq1',
             'des': '', 'override': 4.5},
            {'index': 1, 'id': '2', 'name': '杰尼龟', 'filePath': 'zq2',
             'des': '', 'override': 2.5},
            {'index': 2, 'id': '3', 'name': '妙蛙种子', 'filePath': 'zq3',
             'des': '', 'override': 6.0},
            {'index': 3, 'id': '4', 'name': '皮卡丘', 'filePath': 'zq4',
             'des': '', 'override': 1.5},
        ],
        'selected': selected, 'bet': bet, 'settled': False, 'winner': None,
        'delta': 0, 'times': [], 'started': None,
    }

state = GameState(tables, seed=11)
state.inventory.clear()
state.grant('700008', 1000)
game = RunningPetGame(state)
win = make_session()
# roll 1 <= p*100; winner is selected, then three runner durations.
result = game.settle(win, FakeRng(ints=[1, 101, 110, 101, 110, 101, 110]))
assert result['won'] and result['winner'] == 0
assert result['delta'] == int(100*(4.5-1.0)) == 350
assert state.count('700008') == 1350
assert win['times'][0] == 8.0
assert all(t > 8.0 for t in win['times'][1:])
try:
    game.settle(win, FakeRng())
    raise AssertionError('settled a race twice')
except ValueError:
    pass

loss = make_session(bet=100)
# roll 100 > p*100, then a different runner #2 is selected as winner.
result = game.settle(loss, FakeRng(ints=[100, 101, 110, 101, 110, 101, 110],
                                       ranges=[2]))
assert not result['won'] and result['winner'] == 2
assert result['delta'] == -100
assert state.count('700008') == 1250
assert state.activities['running_pet']['races'] == 2
assert state.activities['running_pet']['wins'] == 1
assert state.activities['running_pet']['streak'] == 0

# getBetMaxMedalCount cap and left/right wrap.
state.inventory['700008'] = 20
assert game.max_bet() == 20
session = make_session(bet=10)
game.adjust_bet(session, +1)
assert session['bet'] == 11
game.adjust_bet(session, -1)
assert session['bet'] == 10
game.adjust_bet(session, -1)
assert session['bet'] == 20
game.adjust_bet(session, +1)
assert session['bet'] == 10
state.inventory['700008'] = 99999
assert game.max_bet() == 9999
assert game.can_enter()

# Session generation is data-backed: four runners and one-decimal original odds.
first = game.new_session()
for contender in first['contenders']:
    assert contender['filePath'] in {row['filePath'] for row in tables['RunningPet'].values()}
    assert 1.5 <= contender['override'] <= 10.0
    assert abs(contender['override']*10-round(contender['override']*10)) < 1e-9

# Stats survive the native save/load format.
with tempfile.TemporaryDirectory() as folder:
    path = Path(folder)/'slot.json'
    state.save(path)
    loaded = GameState.load(tables, path)
    assert loaded.activities['running_pet']['races'] == 2
    assert loaded.activities['running_pet']['wins'] == 1
    assert loaded.count('700008') == 99999

# --- real Tk host UI ---------------------------------------------------------
root = tk.Tk()
root.withdraw()
try:
    app = NativeGame(root, data)
    app.runtime.sequence, app.runtime.file, app.runtime.pending = [], '', None
    app.display_request = None
    app.state.inventory['700008'] = 100
    app.open_ui(Request('openui', 'running-welcome', 1,
                        {'parameters': {'uiid': 39}}))
    assert app.ui_open and 'join_Button' in app.ui_actions
    app.ui_actions['join_Button']()
    assert app.ui_open
    assert app.running_session and len(app.running_session['contenders']) == 4
    assert 'left_Button' in app.ui_actions and 'right_Button' in app.ui_actions
    before = app.running_session['bet']
    app.ui_actions['left_Button']()
    assert app.running_session['bet'] == 100  # wraps down to max
    app.ui_actions['right_Button']()
    assert app.running_session['bet'] == before
    # Select runner 3; this is what the original spawned num_Button does.
    app.running_session['selected'] = 2
    assert app.running_session['contenders'][2]['index'] == 2
    app.close_ui('no')
    assert not app.ui_open

    # Original MedalShop 801 purchase: 1 badge -> 100 running-pet medals.
    app.state.inventory['700002'] = 1
    app.state.inventory['700008'] = 0
    app.open_ui(Request('openui', 'medal-buy', 1,
                        {'parameters': {'uiid': 43}}))
    assert app.ui_open and 'confirm_Button' in app.ui_actions
    app.ui_actions['confirm_Button']()
    assert app.ui_render_args.get('name') == 'RunningPetWelUI'
    assert app.state.count('700002') == 0
    assert app.state.count('700008') == 100
    app.close_ui('no')

    # Result UI uses the original layout and confirm button.
    result_session = make_session(bet=10, selected=0)
    result_session.update({'settled': True, 'winner': 0, 'delta': 35,
                           'times': [8.0, 8.2, 8.3, 8.4]})
    app.running_result = result_session
    app.open_ui(Request('openui', 'running-result', 1,
                        {'parameters': {'uiid': 42}}))
    assert app.ui_open and 'confirm_Button' in app.ui_actions
    app.ui_actions['confirm_Button']()
    assert app.ui_open and app.running_session
    app.close_ui('no')

    # Race UI composes original zq armatures over the original RunningPetMapUI.
    race_session = make_session(bet=10, selected=0)
    race_session.update({'settled': True, 'winner': 0, 'delta': 35,
                         'times': [0.4, 0.5, 0.6, 0.7]})
    app.running_result = race_session
    old_duration = RunningPetGame.WINNER_RUN_TIME
    RunningPetGame.WINNER_RUN_TIME = 0.4
    try:
        app.open_ui(Request('openui', 'running-race', 1,
                            {'parameters': {'uiid': 41}}))
        assert app.ui_open and 'close_Button' in app.ui_actions
        assert getattr(app, 'ui_art_label', None) is not None
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            root.update()
            if app.ui_render_args and app.ui_render_args.get('name') == 'RunningPetResultUI':
                break
            time.sleep(0.02)
        assert getattr(app, 'running_race_frame', None) is not None
        (ROOT/'outputs/verification').mkdir(parents=True, exist_ok=True)
        app.running_race_frame.save(ROOT/'outputs/verification/running-pet-race.png')
        assert app.ui_open
        assert app.ui_render_args.get('name') == 'RunningPetResultUI'
        assert 'confirm_Button' in app.ui_actions
        app.close_ui('no')
    finally:
        RunningPetGame.WINNER_RUN_TIME = old_duration
finally:
    root.destroy()

print('running pet checks passed')
