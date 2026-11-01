"""obsType tree/rock collision, mount ability, map rendering and trial wait resume."""
import json
import sys
import tempfile
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))

from game_state import GameState  # noqa: E402
from mounts import Mounts  # noqa: E402
from original_data import OriginalData  # noqa: E402
from pc_game import NativeGame  # noqa: E402
from task_progress import TaskProgress  # noqa: E402

data = OriginalData(ROOT/'original-1.20.4')
tables = data.tables
map202 = data.load_map(202)
assert map202.obstacles, 'obsType sprites were not parsed'
rock_tiles = [tile for tile, kind in map202.obstacles.items() if kind == 2]
tree_tiles = [tile for tile, kind in map202.obstacles.items() if kind == 1]
assert rock_tiles and tree_tiles
assert map202.terrain_at(rock_tiles[0][0]*64+32, rock_tiles[0][1]*64+32) == 2
assert map202.obstacle_at(rock_tiles[0][0]*64+32, rock_tiles[0][1]*64+32) == 2
assert map202.blocked(rock_tiles[0][0]*64+32, rock_tiles[0][1]*64+32)
old_background = map202.render(.5)
map202.remove_obstacle(*rock_tiles[0])
assert map202.terrain_at(rock_tiles[0][0]*64+32, rock_tiles[0][1]*64+32) == 0
assert not map202.blocked(rock_tiles[0][0]*64+32, rock_tiles[0][1]*64+32)
assert map202.render(.5).tobytes() != old_background.tobytes()

# 护城龙 has obstacleAble 2; 陆行鸟 has obstacleAble 1.
state = GameState(tables, seed=11)
state.rides = ['500005', '500001']
state.ride = 500005
mounts = Mounts(state)
assert mounts.obstacle_ability(2) and not mounts.obstacle_ability(1)
state.ride = 500001
assert mounts.obstacle_ability(1) and not mounts.obstacle_ability(2)
state.ride = 0
assert not mounts.obstacle_ability(2)

# Walk into a rock with 护城龙: it must disappear, grant the obstacle task
# condition, and persist the removed tile.
state = GameState(tables, seed=12)
state.rides, state.ride = ['500005'], 500005
state.main_task, state.main_state = 132, 3
state.task_counts['main:132'] = [0]
tx, ty = rock_tiles[1]
root = tk.Tk()
root.withdraw()
try:
    app = NativeGame(root, data)
    app.state = state
    app.load_map(202, (tx-1)*map202.tw+32, ty*map202.th+32)
    assert app.map.terrain_at(tx*64+32, ty*64+32) == 2
    old_x = app.x
    app.move_to(tx*64+32, ty*64+32)
    assert app.x == tx*64+32 and app.y == ty*64+32
    assert app.map.terrain_at(tx*64+32, ty*64+32) == 0
    assert [int(v) for v in state.removed_obstacles[-1][:3]] == [202, tx, ty]
    assert app.obstacle_fx['type'] == 2
    app.make_frame()
    assert state.task_counts['main:132'] == [1]
    # Without the matching mount the tile stays solid.
    state.ride = 0
    other = rock_tiles[2]
    app.map.remove_obstacle(*other)  # reset for this assertion
    app.load_map(202, (other[0]-1)*64+32, other[1]*64+32)
    before = app.x
    app.move_to(other[0]*64+32, other[1]*64+32)
    assert app.x == before
    assert app.map.obstacle_at(other[0]*64+32, other[1]*64+32) == 2
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()

# A pending trial-ride wait is resumed only after the obstacle is broken.
wait_calls = []
state2 = GameState(tables, seed=13)
state2.rides, state2.ride = ['500005'], 500005
root = tk.Tk()
root.withdraw()
try:
    app = NativeGame(root, data)
    app.state = state2
    app.load_map(202)
    class Pending:
        kind = 'wait'
        data = {'parameters': {'type': 3}}
    app.pending_wait = Pending()
    app.runtime.resume = lambda result=None: wait_calls.append(result)
    t = rock_tiles[3]
    assert app.break_obstacle(2, *t)
    assert app.pending_wait is None
    assert wait_calls == [None]
finally:
    for job in root.tk.call('after', 'info'):
        root.after_cancel(job)
    root.destroy()

# Save/load and a fresh map must reapply removed obstacle tiles.
with tempfile.TemporaryDirectory() as folder:
    path = Path(folder)/'obstacles.json'
    state.save(path)
    loaded = GameState.load(tables, path)
    assert any(int(row[0]) == 202 for row in loaded.removed_obstacles)
    fresh = data.load_map(202)
    for row in loaded.removed_obstacles:
        if int(row[0]) == 202:
            assert fresh.remove_obstacle(int(row[1]), int(row[2])) is not None
    assert fresh.terrain_at(tx*64+32, ty*64+32) == 0

print('obstacle checks passed')