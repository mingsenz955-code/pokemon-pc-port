"""Checks for task-target parsing and real tile-by-tile guidance movement."""
import sys
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from game_state import GameState
from guide import GuideResolver, MapGraph, walk_path
from pc_game import NativeGame

data = OriginalData(ROOT/'original-1.20.4')
state = GameState(data.tables)
state.initialize(2)
resolver = GuideResolver(data, state)

expected = {
    1: ('area', 101, '10101'),
    2: ('npc', 5801, ''),
    3: ('npc', 5801, ''),
    4: ('npc', 5807, ''),
    5: ('area', 5802, '580201'),
    6: ('catch', 102, ''),
    7: ('area', 101, '10103'),
    8: ('area', 105, '10501'),
}
for task, (kind, map_id, area) in expected.items():
    state.main_task, state.main_state = task, 3
    target = resolver.target()
    assert target and target.kind == kind and target.map_id == map_id, (task, target)
    if area:
        assert target.area == area, (task, target)

state.main_task, state.main_state = 1, 3
target = resolver.target()
route = MapGraph(data).route(7401, target.map_id)
assert route == [7401, 7201, 602, 207, 208, 302, 301, 119, 109, 105, 101], route

# Once counters are complete the original submit target wins over the condition.
state.main_task, state.main_state = 2, 4
submit_target = resolver.target()
assert submit_target.kind == 'npc' and submit_target.map_id == 5801, submit_target
state.main_task, state.main_state = 5, 4
submit_target = resolver.target()
assert submit_target.kind == 'exit' and submit_target.map_id == 5802, submit_target

# The area itself is a walkable/trigger rectangle, not just a map marker.
game_map = data.load_map('101')
point = resolver.area_point('10101')
assert point and point[0] == 101
path = walk_path(game_map, (352, 800), (point[1], point[2]),
                 lambda x, y: (x-point[1])**2+(y-point[2])**2 <= 40**2)
assert path, 'no walkable route to area 10101'

root = tk.Tk()
app = NativeGame(root, data)
app.booting = False
app.runtime.file = ''
app.dialogue = None
app.display_request = None
app.pending_wait = None
app.steps = []
app.state.initialize(2)
app.state.main_task, app.state.main_state = 1, 3
app.load_map(101, 352, 800)
app.exit_time = 0
app.guide.start()
for _ in range(500):
    app.guide.step()
    if not app.guide.active:
        break
inside = any(o['group'] == 'eventLayer' and o.get('name') == '10101'
             and float(o.get('x', 0)) <= app.x < float(o.get('x', 0))+float(o.get('width', 64))
             and float(o.get('y', 0)) <= app.y < float(o.get('y', 0))+float(o.get('height', 64))
             for o in app.map.objects)
assert inside, (app.map_id, app.x, app.y, app.guide.message)
assert not app.guide.active
area_position = [app.map_id, round(app.x), round(app.y)]

# A real map transition through the original exit object.
app.state.main_task, app.state.main_state = 1, 3
app.load_map(7401, 1152, 1900)
app.exit_time = 0
app.guide.start()
for _ in range(240):
    app.guide.step()
    if app.map_id == 7201:
        break
assert app.map_id == 7201, (app.map_id, app.x, app.y, app.guide.message)
assert 0 <= app.x <= app.map.width*64 and 0 <= app.y <= app.map.height*64
for _ in range(20):
    app.guide.step()
assert app.guide.active, app.guide.message
assert app.guide.waypoints, 'guide did not rebuild a path after the map transition'

# Every map edge on the verified route must have a valid, walkable spawn.
graph = MapGraph(data)
blocked_arrivals = 0
for source, target_map in zip(route, route[1:]):
    edge = graph.edge(source, target_map)
    assert edge, (source, target_map)
    source_map = data.load_map(str(source))
    exits = [o for o in source_map.objects if o.get('name') == edge['from_exit']
             and o.get('props', {}).get('toExit') == edge['to_exit']]
    assert exits, (source, edge)
    destination = data.load_map(str(target_map))
    arrivals = [o for o in destination.objects if o.get('name') == edge['to_exit']
                and 'toExit' in o.get('props', {})]
    assert arrivals, (target_map, edge['to_exit'])
    sx, sy = app.exit_spawn(destination, arrivals[0])
    assert 32 <= sx <= destination.width*64-32 and 32 <= sy <= destination.height*64-32, (source, target_map, sx, sy)
    if destination.blocked(sx, sy):
        blocked_arrivals += 1

# Walk to an original NPC on the next map and stop in interaction range.
app.state.main_task, app.state.main_state = 2, 3
app.load_map(5801, 640, 900)
app.exit_time = 0
app.guide.start()
for _ in range(700):
    app.guide.step()
    if not app.guide.active:
        break
npc_target = app.guide.target
assert not app.guide.active, app.guide.message
assert (app.x-npc_target.x)**2+(app.y-npc_target.y)**2 <= 150**2, (app.x, app.y, npc_target)
app.guide_ui()
root.update()
for child in list(root.winfo_children()):
    if isinstance(child, tk.Toplevel):
        child.destroy()
root.destroy()

report = {'targets': {str(k): list(v) for k, v in expected.items()},
          'route_7401_to_101': route, 'area_path_tiles': len(path),
          'area_arrival': area_position, 'exit_transition': True,
          'npc_arrival_distance': round(((app.x-npc_target.x)**2+(app.y-npc_target.y)**2)**.5),
          'blocked_route_arrivals': blocked_arrivals}
(ROOT/'outputs/verification/guide-runtime-checks.json').write_text(
    __import__('json').dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(report)