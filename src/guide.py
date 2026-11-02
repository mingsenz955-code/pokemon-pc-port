"""Original-task guidance: resolve a task objective to a map/area/NPC and walk there.

The original task tables encode five spatial objective shapes:

* conditionType 1: ``area`` id such as ``10101`` (map 101, event area 01)
* conditionType 2: choose one of ``targetNpcs``
* conditionType 3: catch a pet; the third value is the map id (``-1`` wildcard)
* conditionType 4: talk to an NPC id such as ``580101``
* conditionType 5: fight (battle type, result, NPC battle id, pet id)
* conditionType 6: break an obstacle type
* conditionType 7: enter a map id

The resolver below is deliberately data-only.  It never invents coordinates: when
an object is missing the guide reports that instead of walking to a guessed spot.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
import time

from mounts import Mounts


def integers(value):
    return [int(v) for v in str(value).split(',') if str(v).strip()]


@dataclass
class GuideTarget:
    kind: str
    label: str
    map_id: int = 0
    x: float = 0
    y: float = 0
    task_kind: str = ''
    task_id: str = ''
    task_name: str = ''
    description: str = ''
    detail: str = ''
    area: str = ''
    radius: float = 60
    npc_id: str = ''

    def __bool__(self):
        return bool(self.map_id or self.kind in {'level', 'item', 'pet'})


class GuideResolver:
    def __init__(self, data, state):
        self.data, self.state = data, state
        self.tables = data.tables
        self._npc = None

    def area_point(self, area_id):
        area = str(area_id)
        if len(area) < 3:
            return None
        map_id = int(area[:-2])
        if str(map_id) not in self.tables['VillageMap']:
            return None
        game_map = self.data.load_map(str(map_id))
        for obj in game_map.objects:
            if obj['group'] == 'eventLayer' and str(obj.get('name')) == area:
                x = float(obj.get('x', 0))+float(obj.get('width', 64))/2
                y = float(obj.get('y', 0))+float(obj.get('height', 64))/2
                return map_id, x, y, obj
        # A missing area must not become a made-up coordinate.
        return None

    def npc_locations(self):
        if self._npc is not None:
            return self._npc
        self._npc = {}
        for map_id, row in self.tables['VillageMap'].items():
            try:
                game_map = self.data.load_map(map_id)
            except (OSError, ValueError):
                continue
            # eventLayer entries with npcId are the authoritative placement.
            for obj in game_map.objects:
                npc_id = str(obj.get('props', {}).get('npcId', ''))
                if npc_id and npc_id != '0':
                    x = float(obj.get('x', 0))+float(obj.get('width', 64))/2
                    y = float(obj.get('y', 0))+float(obj.get('height', 64))/2
                    self._npc.setdefault(npc_id, []).append((int(map_id), x, y, 'event'))
            for obj in game_map.objects:
                if obj['group'] != 'spriteLayer' or 'toExit' in obj.get('props', {}):
                    continue
                name = str(obj.get('name', ''))
                # A hidden TMX actor can be revealed by the plot later. State 0
                # is its initial visibility, not evidence that it has no location.
                if not name:
                    continue
                x = float(obj.get('x', 0))+float(obj.get('width', 64))/2
                y = float(obj.get('y', 0))
                self._npc.setdefault(name, []).append((int(map_id), x, y, 'sprite'))
        return self._npc

    def npc_point(self, npc_id):
        locations = self.npc_locations().get(str(npc_id), [])
        if not locations:
            return None
        # Prefer an event placement over a decorative duplicate.
        locations = sorted(locations, key=lambda item: (item[3] != 'event', item[0]))
        return locations[0][0], locations[0][1], locations[0][2], locations[0]

    def catch_point(self, pet_id, pet_kind, map_id):
        requested = int(map_id) if map_id > 0 else None
        target = None
        for mid, row in self.tables['VillageMap'].items():
            if requested is not None and int(mid) != requested:
                continue
            enemies = [v for v in str(row.get('enemyIds', '')).split(',') if v and v != '0']
            if not enemies:
                continue
            # enemyIds references VillageEnemy, not Pet. Both constraints must
            # match the same encounter, rather than two different pets.
            pets = [self.tables['Pet'].get(str(self.tables['VillageEnemy'].get(e, {}).get('petId')), {})
                    for e in enemies]
            if not any(pet and (pet_id == -1 or str(pet.get('keyId')) == str(pet_id))
                       and (pet_kind == -1 or str(pet.get('kind')) == str(pet_kind))
                       for pet in pets):
                continue
            target = int(mid)
            break
        if not target:
            return None
        game_map = self.data.load_map(str(target))
        # A wild-pet objective has no fixed point; the map centre is only a
        # navigation anchor, never a claim that the pet is at that tile.
        return target, game_map.width*32, game_map.height*32, None

    def from_task(self, category, key, row, status):
        name = str(row.get('name', ''))
        description = str(row.get('des', ''))
        condition_type = int(row.get('conditionType', 0))
        conditions = integers(row.get('conditions', '0'))
        # State 4 means the counters are complete; target the submit target first.
        if status == 4:
            submitted = str(row.get('submitNpcs', '0'))
            if submitted and submitted != '0':
                point = self.npc_point(submitted)
                if point:
                    return GuideTarget('npc', f'提交任务：{name}', point[0], point[1], point[2],
                                       category, key, name, description,
                                       f'找 NPC {submitted} 提交任务', radius=90, npc_id=submitted)
            submitted_exit = str(row.get('submitExits', '0'))
            if submitted_exit and submitted_exit != '0':
                mid = exit_destination_map(self.tables, self.data, submitted_exit)
                if mid:
                    game_map = self.data.load_map(str(mid))
                    return GuideTarget('exit', f'提交任务：{name}', mid, game_map.width*32,
                                       game_map.height*32, category, key, name, description,
                                       f'通过原出口 {submitted_exit} 前往地图 {mid}', area=submitted_exit)
        if condition_type == 1 and conditions:
            area = str(conditions[0])
            point = self.area_point(area)
            if point:
                return GuideTarget('area', f'{name}：区域 {area}', point[0], point[1], point[2],
                                   category, key, name, description,
                                   f'进入地图 {point[0]} 的原版区域 {area}', area=area, radius=40)
        if condition_type == 2:
            for npc_id in str(row.get('targetNpcs', '')).split(','):
                npc_id = npc_id.strip()
                if not npc_id or npc_id == '0':
                    continue
                point = self.npc_point(npc_id)
                if point:
                    return GuideTarget('npc', f'{name}：收集任务目标', point[0], point[1], point[2],
                                       category, key, name, description,
                                       f'前往任务配置的 NPC {npc_id}', radius=90, npc_id=npc_id)
        if condition_type == 3 and len(conditions) >= 3:
            point = self.catch_point(conditions[0], conditions[1], conditions[2])
            if point:
                return GuideTarget('catch', f'{name}：捕捉宠物', point[0], point[1], point[2],
                                   category, key, name, description,
                                   f'前往地图 {point[0]} 捕捉原版目标宠物', radius=90)
        if condition_type == 4 and conditions:
            npc_id = str(conditions[0])
            point = self.npc_point(npc_id)
            if point:
                return GuideTarget('npc', f'{name}：找 NPC {npc_id}', point[0], point[1], point[2],
                                   category, key, name, description,
                                   f'与 NPC {npc_id} 对话', radius=90, npc_id=npc_id)
        if condition_type == 5 and conditions:
            for npc_id in integers(row.get('targetNpcs', '0')):
                point = self.npc_point(npc_id)
                if point:
                    return GuideTarget('npc', f'{name}：挑战 NPC {npc_id}', *point[:3],
                                       category, key, name, description,
                                       f'与 NPC {npc_id} 战斗；胜负由实际战斗结算', radius=90, npc_id=str(npc_id))
            return None
        if condition_type == 6 and conditions:
            return GuideTarget('obstacle', f'{name}：破除障碍', task_kind=category,
                               task_id=key, task_name=name, description=description,
                               detail='使用对应坐骑破除任务要求的障碍；任务表未指定固定地图。')
        if condition_type == 7 and conditions:
            mid = int(conditions[0])
            if str(mid) in self.tables['VillageMap']:
                game_map = self.data.load_map(str(mid))
                return GuideTarget('map', f'{name}：前往 {game_map.info["name"]}', mid,
                                   game_map.width*32, game_map.height*32, category, key, name,
                                   description, f'进入地图 {mid}', radius=90)
        return None

    def targets(self):
        result = []
        main = self.tables['MainTask'].get(str(self.state.main_task))
        if main and self.state.main_state in (3, 4):
            target = self.from_task('main', str(self.state.main_task), main, self.state.main_state)
            if target:
                result.append(target)
        for key, status in self.state.branch_states.items():
            if status not in (3, 4):
                continue
            row = self.tables['BranchTask'].get(str(key))
            if not row:
                continue
            target = self.from_task('branch', str(key), row, status)
            if target:
                result.append(target)
        return result

    def target(self):
        targets = self.targets()
        return targets[0] if targets else None


def exit_map_id(tables, exit_id):
    value = str(exit_id)
    for length in (2, 1):
        candidate = value[:-length]
        if candidate in tables['VillageMap']:
            return int(candidate)
    return 0


def exit_destination_map(tables, data, exit_id):
    """Resolve a source exit (e.g. 10106) through its original toExit target."""
    value = str(exit_id)
    row = tables['VillageExit'].get(value)
    if row and str(row.get('toExit', '0')) != '0':
        return exit_map_id(tables, row['toExit'])
    # Some original exits only exist as TMX objects, not VillageExit rows.
    for mid in tables['VillageMap']:
        try:
            game_map = data.load_map(mid)
        except (OSError, ValueError):
            continue
        for obj in game_map.objects:
            if obj['group'] == 'spriteLayer' and str(obj.get('name')) == value and 'toExit' in obj.get('props', {}):
                return exit_map_id(tables, obj['props']['toExit'])
    return 0


class MapGraph:
    def __init__(self, data):
        self.data = data
        self.edges = {}
        owner = {}
        for mid, row in data.tables['VillageMap'].items():
            for exit_id in str(row.get('exitIds', '')).split(','):
                if exit_id and exit_id != '0':
                    owner[exit_id] = int(mid)
        for mid in data.tables['VillageMap']:
            try:
                game_map = data.load_map(mid)
            except (OSError, ValueError):
                continue
            for obj in game_map.objects:
                if obj['group'] != 'spriteLayer' or 'toExit' not in obj.get('props', {}):
                    continue
                target_exit = str(obj['props']['toExit'])
                target_map = owner.get(target_exit)
                if not target_map or target_map == int(mid):
                    continue
                self.edges.setdefault(int(mid), {}).setdefault(target_map, {
                    'from_exit': str(obj.get('name')), 'to_exit': target_exit,
                    'target_map': target_map,
                })

    def route(self, start, goal):
        start, goal = int(start), int(goal)
        if start == goal:
            return [start]
        queue, previous = deque([start]), {start: None}
        while queue:
            current = queue.popleft()
            for neighbour in self.edges.get(current, {}):
                if neighbour in previous:
                    continue
                previous[neighbour] = current
                if neighbour == goal:
                    path = [goal]
                    while path[-1] != start:
                        path.append(previous[path[-1]])
                    return list(reversed(path))
                queue.append(neighbour)
        return []

    def edge(self, source, target):
        return self.edges.get(int(source), {}).get(int(target))


def _tile_center(tx, ty):
    return tx*64+32, ty*64+32


def walk_path(game_map, start, goal, predicate, mounts=None, limit=40000):
    """BFS over walkable tile centres; returns world-space waypoints.

    ``goal`` is only used when ``predicate`` is None; predicates let NPC/exit
    targets stop next to a large object's occupied tile.
    """
    width, height = game_map.width, game_map.height
    sx, sy = int(start[0]//64), int(start[1]//64)
    sx, sy = max(0, min(width-1, sx)), max(0, min(height-1, sy))

    def passable(tx, ty):
        if not (0 <= tx < width and 0 <= ty < height):
            return False
        x, y = _tile_center(tx, ty)
        return not game_map.blocked(x, y, mounts)

    if not passable(sx, sy):
        found = None
        for radius in range(1, 8):
            for dx in range(-radius, radius+1):
                for dy in range(-radius, radius+1):
                    if passable(sx+dx, sy+dy):
                        found = (sx+dx, sy+dy)
                        break
                if found:
                    break
            if found:
                break
        if not found:
            return []
        sx, sy = found

    gx, gy = int(goal[0]//64), int(goal[1]//64)
    queue = deque([(sx, sy)])
    previous = {(sx, sy): None}
    end = None
    while queue and len(previous) < limit:
        tx, ty = queue.popleft()
        x, y = _tile_center(tx, ty)
        if predicate(x, y) if predicate else (tx, ty) == (gx, gy):
            end = (tx, ty)
            break
        for nx, ny in ((tx+1, ty), (tx-1, ty), (tx, ty+1), (tx, ty-1)):
            if (nx, ny) in previous or not passable(nx, ny):
                continue
            previous[(nx, ny)] = (tx, ty)
            queue.append((nx, ny))
    if end is None:
        return []
    path = []
    node = end
    while node is not None and node != (sx, sy):
        path.append(_tile_center(*node))
        node = previous[node]
    return list(reversed(path))


class Guide:
    STEP = 12

    def __init__(self, app):
        self.app = app
        self.resolver = GuideResolver(app.data, app.state)
        self.graph = MapGraph(app.data)
        self.target = None
        self.waypoints = []
        self.route = []
        self.active = False
        self.message = ''
        self._last_map = None
        self._last_time = 0
        self._visited_exit = None
        self._stuck = 0

    def refresh(self):
        self.target = self.resolver.target()
        return self.target

    def rebind(self, state):
        """A loaded save replaces the GameState object the resolver holds."""
        self.resolver.state = state
        self.resolver._npc = None
        self.target = None
        self.stop('')

    def start(self, target=None):
        self.target = target or self.refresh()
        if not self.target:
            self.message = '当前没有可解析的空间任务目标。'
            self.active = False
            return False
        if not self.target.map_id:
            self.message = self.target.detail or '该目标不在地图上，无法自动前往。'
            self.active = False
            return False
        self.active = True
        self.waypoints = []
        self.route = []
        self._last_map = None
        self._visited_exit = None
        self._stuck = 0
        self._last_time = time.monotonic()
        self._task_stamp = (self.app.state.main_task, self.app.state.main_state)
        self.message = f'正在前往 {self.target.label}'
        return True

    def stop(self, message=''):
        self.active = False
        self.waypoints = []
        self.route = []
        if message:
            self.message = message

    def point(self):
        if self.waypoints:
            return self.waypoints[0]
        if self.active and self.target and self.target.map_id == self.app.map_id:
            return self.target.x, self.target.y
        return None

    def _route(self):
        self.route = self.graph.route(self.app.map_id, self.target.map_id)
        if not self.route:
            self.message = f'地图 {self.app.map_id} 到 {self.target.map_id} 没有已核验的出口路线。'
            self.stop()
            return False
        return True

    def _exit_waypoints(self):
        next_map = self.route[1]
        edge = self.graph.edge(self.app.map_id, next_map)
        if not edge:
            self.message = '出口图与地图表不一致，停止自动移动。'
            self.stop()
            return []
        objects = [o for o in self.app.map.objects
                   if o['group'] == 'spriteLayer' and o.get('name') == edge['from_exit']
                   and o.get('props', {}).get('toExit') == edge['to_exit']]
        if not objects:
            self.message = f'当前地图缺少出口对象 {edge["from_exit"]}，停止自动移动。'
            self.stop()
            return []
        obj = objects[0]
        x, y, w, h = (float(obj.get('x', 0)), float(obj.get('y', 0)),
                      float(obj.get('width', 64)), float(obj.get('height', 64)))
        def inside(px, py):
            return x <= px < x+w and y <= py < y+h
        path = walk_path(self.app.map, (self.app.x, self.app.y), (x+w/2, y+h/2), inside,
                         mounts=Mounts(self.app.state))
        if not path and inside(self.app.x, self.app.y):
            return []
        if not path:
            self.message = f'无法走到出口 {edge["from_exit"]}，可能被地形阻挡。'
            self.stop()
        return path

    def _target_waypoints(self):
        target = self.target
        def reached(px, py):
            if target.kind == 'npc':
                return self._npc_reached(px, py)
            if target.kind == 'area':
                obj = next((o for o in self.app.map.objects if o['group'] == 'eventLayer'
                            and str(o.get('name')) == target.area), None)
                if obj:
                    return (float(obj['x']) <= px < float(obj['x'])+float(obj.get('width', 64))
                            and float(obj['y']) <= py < float(obj['y'])+float(obj.get('height', 64)))
            return (px-target.x)**2 + (py-target.y)**2 <= target.radius**2
        path = walk_path(self.app.map, (self.app.x, self.app.y), (target.x, target.y), reached,
                         mounts=Mounts(self.app.state))
        if not path and reached(self.app.x, self.app.y):
            return []
        if not path:
            self.message = f'无法走到 {target.label}，可能被地形阻挡。'
            self.stop()
        return path

    def _npc_reached(self, x, y):
        target = self.target
        world = self.app.map
        dx = abs(int(x//world.tw)-int(target.x//world.tw))
        dy = abs(int(y//world.th)-int(target.y//world.th))
        centered = (abs(x-(int(x//world.tw)+.5)*world.tw) <= 2
                    and abs(y-(int(y//world.th)+.5)*world.th) <= 2)
        return dx+dy == 1 and centered

    def _arrived(self):
        target = self.target
        if target.kind == 'npc':
            if self._npc_reached(self.app.x, self.app.y):
                dx, dy = target.x-self.app.x, target.y-self.app.y
                self.app.face = ('standleft' if dx < 0 else 'standright') if abs(dx) > abs(dy) else (
                    'standup' if dy < 0 else 'standdown')
                self.stop(f'已到达 {target.label}，按空格对话。')
                return True
        elif target.kind == 'area':
            for obj in self.app.map.objects:
                if obj['group'] == 'eventLayer' and str(obj.get('name')) == target.area:
                    x, y, w, h = (float(obj.get('x', 0)), float(obj.get('y', 0)),
                                  float(obj.get('width', 64)), float(obj.get('height', 64)))
                    if x <= self.app.x < x+w and y <= self.app.y < y+h:
                        self.stop(f'已进入原版区域 {target.area}，任务条件已触发。')
                        return True
        elif target.kind in {'catch', 'map', 'exit'}:
            if self.app.map_id == target.map_id:
                self.stop(f'已到达地图 {target.map_id}：{self.app.map.info["name"]}。')
                return True
        return False

    def step(self, seconds=None):
        if not self.active or not self.target:
            return
        app = self.app
        now = time.monotonic()
        seconds = min(.1, max(0, seconds if seconds is not None else 1/60))
        self._last_time = now
        if (app.battle or app.runtime.running or app.dialogue is not None or app.display_request
                or getattr(app, 'pending_wait', None) or getattr(app, 'ui_open', False)):
            self.waypoints = []
            return
        stamp = (app.state.main_task, app.state.main_state)
        if self.target.task_kind == 'main' and stamp != getattr(self, '_task_stamp', None):
            self.start(self.resolver.target())
            if not self.active:
                return
        if self.target.kind == 'npc' and self.target.map_id == app.map_id and self.target.npc_id:
            actor = next((a for a in app.actors() if str(a[0]) == self.target.npc_id), None)
            if actor:
                if (int(actor[2]//app.map.tw), int(actor[3]//app.map.th)) != (
                        int(self.target.x//app.map.tw), int(self.target.y//app.map.th)):
                    self.waypoints = []
                self.target.x, self.target.y = actor[2], actor[3]
        if self._last_map != app.map_id:
            self._last_map = app.map_id
            self.waypoints = []
            if not self._route():
                return
        if app.map_id == self.target.map_id and self._arrived():
            return
        if app.map_id != self.target.map_id:
            if not self.route or self.route[0] != app.map_id:
                if not self._route():
                    return
            if not self.waypoints:
                self.waypoints = self._exit_waypoints()
                if not self.waypoints:
                    if self.active:
                        app.try_exit()
                    return
        elif not self.waypoints:
            self.waypoints = self._target_waypoints()
            if not self.waypoints:
                if self._arrived():
                    return
                return
        # Walk to the next tile centre; app.move_to applies the original mount
        # terrain rules, so the guide cannot tunnel through blocked tiles.
        before = (app.x, app.y)
        distance = app.movement_speed()*seconds
        while self.waypoints and distance > 0:
            wx, wy = self.waypoints[0]
            dx, dy = wx-app.x, wy-app.y
            if abs(dx) < 1e-6 and abs(dy) < 1e-6:
                self.waypoints.pop(0)
                continue
            step = min(distance, abs(dx) if abs(dx) >= abs(dy) else abs(dy))
            previous = (app.x, app.y)
            if abs(dx) >= abs(dy):
                app.move_to(app.x+math.copysign(step, dx), app.y)
            else:
                app.move_to(app.x, app.y+math.copysign(step, dy))
            if previous == (app.x, app.y):
                break
            distance -= step
            if abs(wx-app.x) < 1e-6 and abs(wy-app.y) < 1e-6:
                self.waypoints.pop(0)
        if abs(app.x-before[0]) < .01 and abs(app.y-before[1]) < .01:
            self._stuck += 1
            if self._stuck > 120:
                self.stop('自动移动被地形或动态对象阻挡，已停止。')
                return
        else:
            self._stuck = 0
        if app.map_id != self._last_map:
            self.waypoints = []
            return
        # Exit rectangles are triggers, not just waypoints: keep calling the
        # original transition while standing on one.
        if app.map_id != self.target.map_id:
            app.try_exit()
