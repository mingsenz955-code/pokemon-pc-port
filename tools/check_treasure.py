"""Treasure map purchase, magnifier reveal, map chest and UI contract."""
import json
import sys
import tempfile
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))

from game_state import GameState  # noqa: E402
from original_data import OriginalData  # noqa: E402
from pc_game import NativeGame  # noqa: E402
from treasure import TreasureHunt  # noqa: E402
from event_runtime import Request  # noqa: E402

data = OriginalData(ROOT/'original-1.20.4')
tables = data.tables

# --- table-driven pure rules -------------------------------------------------
state = GameState(tables, seed=7)
state.grant('700002', 50)
hunt = TreasureHunt(state)
row = tables['Treasure']['1']
entry = hunt.buy('1')
assert entry['map_id'] == '102'
assert entry['pos_id'] in set(str(v) for v in str(row['chestPoss']).split(','))
assert state.count('700002') == 45
assert state.count('220007') == 3
assert not entry['revealed']
assert not hunt.visible_on(entry['map_id'])
try:
    hunt.buy('1')
    raise AssertionError('duplicate active map was purchased')
except ValueError:
    pass
assert state.count('700002') == 45
assert state.count('220007') == 3
context = {'map_id': entry['map_id'], 'viewport': (entry['x']-100, entry['y']-100, entry['x']+100, entry['y']+100)}
hunt.use_magnifier(**context)
assert state.count('220007') == 2
assert entry['revealed']
assert hunt.visible_on('102')
try:
    hunt.use_magnifier(**context)
    raise AssertionError('revealed treasure was searched twice')
except ValueError:
    pass
item, count = hunt.open(entry['pos_id'])
assert item in set(str(v) for v in tables['TChest'][entry['chest_id']]['itemIds'].split(','))
assert count > 0
assert not hunt.entries()
try:
    hunt.open(entry['pos_id'])
    raise AssertionError('opened treasure opened twice')
except ValueError:
    pass

# insufficient money is atomic
poor = GameState(tables, seed=8)
poor.inventory.clear()
try:
    TreasureHunt(poor).buy('1')
    raise AssertionError('bought without badges')
except ValueError:
    pass
assert not poor.activities.get('treasure_maps')

# active treasure state survives a native save/load round trip
persist = GameState(tables, seed=9)
persist.grant('700002', 10)
saved = TreasureHunt(persist).buy('2')
with tempfile.TemporaryDirectory() as folder:
    path = Path(folder)/'slot.json'
    persist.save(path)
    loaded = GameState.load(tables, path)
    restored = TreasureHunt(loaded).active()
    assert restored and restored['pos_id'] == saved['pos_id']
    assert restored['map_id'] == saved['map_id']

# --- real Tk host UI ---------------------------------------------------------
root = tk.Tk()
root.withdraw()
try:
    app = NativeGame(root, data)
    app.runtime.sequence, app.runtime.file, app.runtime.pending = [], '', None
    app.display_request = None
    app.state.grant('700002', 20)
    app.state.activities.pop('treasure_maps', None)
    app.state.inventory['220007'] = 0
    app.open_ui(Request('openui', 'treasure-test', 1,
                        {'parameters': {'uiid': 24, 'par1': 1}}))
    assert app.ui_actions.get('use_Button')
    app.ui_actions['use_Button']()
    assert app.ui_open and '没有藏宝图' in app.ui_info.get()
    app.close_ui()

    app.open_ui(Request('openui', 'treasure-buy', 1,
                        {'parameters': {'uiid': 37, 'par1': 1}}))
    assert app.ui_actions.get('buy_Button')
    app.ui_actions['buy_Button']()
    assert app.state.count('700002') == 15
    assert app.state.count('220007') == 3
    active = TreasureHunt(app.state).active()
    assert active and not active['revealed']
    app.load_map(active['map_id'], active['x'], active['y'])
    app.open_ui(Request('openui', 'treasure-test', 1,
                        {'parameters': {'uiid': 24, 'par1': 1}}))
    app.ui_actions['use_Button']()
    assert app.state.count('220007') == 2
    active = TreasureHunt(app.state).active()
    assert active and active['revealed']
    app.runtime.sequence, app.runtime.file, app.runtime.pending = [], '', None
    app.display_request = None
    app.screen_black = False
    app.load_map(active['map_id'])
    ids = [a[0] for a in app.actors() if a[0].startswith('treasure:')]
    assert f'treasure:{active["pos_id"]}' in ids
    app.x, app.y = active['x'], active['y']
    app.interact()
    assert not TreasureHunt(app.state).entries()
    assert app.chest_fx and 'fx:treasure' in [a[0] for a in app.actors()]
    assert (any('宝藏获得' in str(issue) for issue in app.state.audit) or app.event_issue
            or (app.ui_open and app.ui_render_args['name'] == 'GetItemUI'))
    if app.ui_open:
        app.close_ui()
    app.x = active['x'] - 100
    app.screen_black = False
    fx_shot = ROOT/'outputs/verification/treasure-open-fx.png'
    app.make_frame().save(fx_shot)
    app.chest_fx['age'] = 25
    app.tick()
    assert app.chest_fx is None

    # The two internal layouts reachable from TreasureMapUILayer are now
    # real host screens too: buy confirmation and clue confirmation.
    app.open_ui(Request('openui', 'treasure-buy', 1,
                        {'parameters': {'uiid': 37, 'par1': 1}}))
    assert app.ui_actions.get('buy_Button')
    app.ui_actions['buy_Button']()
    assert TreasureHunt(app.state).active()
    app.open_ui(Request('openui', 'treasure-tip', 1,
                        {'parameters': {'uiid': 38}}))
    assert app.ui_actions.get('confirm_Button')
    app.ui_actions['confirm_Button']()
    assert not app.ui_open

    # Render the actual map with the revealed chest actor.
    active = TreasureHunt(app.state).active()
    assert active and not active['revealed']
    TreasureHunt(app.state).use_magnifier(map_id=active['map_id'], viewport=(active['x']-100, active['y']-100, active['x']+100, active['y']+100))
    app.runtime.sequence, app.runtime.file, app.runtime.pending = [], '', None
    app.display_request = None
    app.screen_black = False
    app.load_map(active['map_id'])
    app.x, app.y = active['x'] - 100, active['y']
    frame = app.make_frame()
    assert frame.size == (app.WIDTH, app.HEIGHT)
    shot = ROOT/'outputs/verification/treasure-map.png'
    shot.parent.mkdir(parents=True, exist_ok=True)
    frame.save(shot)

    app.open_ui(Request('openui', 'treasure-test', 1,
                        {'parameters': {'uiid': 24, 'par1': 1}}))
    app.ui_actions['giveUp_Button']()
    assert TreasureHunt(app.state).entries()
    app.ui_actions['confirm_Button']()
    assert not TreasureHunt(app.state).entries()
    app.ui_actions['close_Button']()
    assert not app.ui_open

    # The original talk event drives UI 24's closeui yes branch, not just a
    # direct button call.
    event_app = NativeGame(root, data)
    event_app.runtime.file = ''
    event_app.display_request = None
    event_app.state.grant('700002', 20)
    event_app.state.activities.pop('treasure_maps', None)
    event_app.state.inventory['220007'] = 0
    TreasureHunt(event_app.state).buy('1')
    event_app.runtime.start('pEventTalk50319.json')
    event_app.drive()
    for _ in range(6):
        if event_app.ui_open:
            break
        event_app.next_step()
    assert event_app.ui_open
    event_app.ui_actions['use_Button']()
    while event_app.dialogue is not None:
        event_app.next_step()
    assert not event_app.runtime.running
    assert TreasureHunt(event_app.state).active()
    print('UI 24 purchase/search and map chest: PASS')
finally:
    root.destroy()

report = {
    'treasure_buy': True,
    'magnifier_consumption': True,
    'random_candidate': entry['pos_id'],
    'tchest_reward': [item, count],
    'map_actor': True,
    'double_open_rejected': True,
    'insufficient_money_atomic': True,
    'save_round_trip': True,
    'ui24_flow': True,
    'event_flow': True,
    'give_up_ui': True,
    'treasure_buy_ui': True,
    'treasure_tip_ui': True,
}
out = ROOT/'outputs/verification/treasure.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(report)
