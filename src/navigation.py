"""Original exit graph, introductory main-task arrow and native tile walking.

searchShortestExit @ 0x2dfbd0 increments GScore by one per exit; FScore is
GScore. Introductory guide icons are restricted to main task IDs <=17.
Fine path tie-breaking and all sprite obstacle interactions remain under audit.
"""
from collections import deque
from functools import lru_cache
import heapq
import math
import time

from game_state import numbers
from mounts import Mounts


class WorldRoutes:
    def __init__(self, tables):
        self.tables = tables
        self.graph = {}
        for key, row in tables['VillageMap'].items():
            links = []
            for exit_id in numbers(row['exitIds']):
                exit_row = tables.get('VillageExit', {}).get(str(exit_id))
                if not exit_row:
                    continue
                landing = int(exit_row['toExit'])
                destination = landing//100
                if str(destination) in tables['VillageMap']:
                    links.append((destination, exit_id, landing))
            self.graph[int(key)] = links

    @lru_cache(maxsize=1024)
    def route(self, source, target):
        source, target = int(source), int(target)
        if source == target:
            return ()
        queue, parents = deque([source]), {source: None}
        while queue:
            current = queue.popleft()
            for destination, exit_id, landing in self.graph.get(current, []):
                if destination in parents:
                    continue
                parents[destination] = (current, exit_id, landing)
                if destination == target:
                    result, cursor = [], target
                    while cursor != source:
                        previous, leave, arrive = parents[cursor]
                        result.append((previous, leave, cursor, arrive))
                        cursor = previous
                    return tuple(reversed(result))
                queue.append(destination)
        return None

    def nearest_shop(self, source, shop_type):
        candidates = []
        for key, row in self.tables['VillageMap'].items():
            if int(row.get('shopType', 0)) != int(shop_type):
                continue
            route = self.route(int(source), int(key))
            if route is not None:
                candidates.append((len(route), int(key)))
        return min(candidates)[1] if candidates else None


def object_center(obj, tile_width=64, tile_height=64):
    if obj.get('gid'):
        return float(obj['x'])+tile_width/2, float(obj['y'])
    return (float(obj.get('x', 0))+float(obj.get('width', tile_width))/2,
            float(obj.get('y', 0))+float(obj.get('height', tile_height))/2)


def main_task_target(state, map_id):
    """Return (object category, object ID, destination map), per original subclasses."""
    if state.main_task > 17 or state.main_state not in (3, 4):
        return None
    row = state.tables['MainTask'].get(str(state.main_task))
    if not row:
        return None
    kind, status = int(row['conditionType']), state.main_state
    values = numbers(row['conditions'])
    if kind == 1 and status == 3:
        targets = [key for key in values if key > 0]
        return ('area', targets[-1], targets[-1]//100) if targets else None
    if kind == 7 and status == 3:
        return ('map', 0, values[-1]) if values else None
    if kind == 3 and status == 3:
        targets = [values[i] for i in range(2, len(values), 3)
                   if values[i] > 0 and values[i] != int(map_id)]
        return ('map', 0, targets[-1]) if targets else None
    if kind == 4 or status == 4 and kind in (2, 3, 5):
        targets = [key for key in numbers(row['submitNpcs']) if key > 0]
    elif kind == 5 and status == 3:
        targets = [key for key in numbers(row['targetNpcs']) if key > 0]
    else:
        targets = []
    return ('npc', targets[-1], targets[-1]//100) if targets else None


def tile_path(world, start, goal, mounts):
    """Cardinal tile path respecting the same mount policy as manual movement."""
    source = (int(start[0]//world.tw), int(start[1]//world.th))
    target = (int(goal[0]//world.tw), int(goal[1]//world.th))
    if not (0 <= target[0] < world.width and 0 <= target[1] < world.height):
        return None
    frontier, costs, parents = [(0, 0, source)], {source: 0}, {source: None}
    sequence = 0
    while frontier:
        _, _, current = heapq.heappop(frontier)
        if current == target:
            path = []
            while current != source:
                path.append(((current[0]+.5)*world.tw, (current[1]+.5)*world.th))
                current = parents[current]
            return list(reversed(path))
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            neighbor = (current[0]+dx, current[1]+dy)
            if world.blocked((neighbor[0]+.5)*world.tw, (neighbor[1]+.5)*world.th, mounts):
                continue
            candidate = costs[current]+1
            if candidate >= costs.get(neighbor, math.inf):
                continue
            parents[neighbor], costs[neighbor] = current, candidate
            sequence += 1
            estimate = abs(neighbor[0]-target[0])+abs(neighbor[1]-target[1])
            heapq.heappush(frontier, (candidate+estimate, sequence, neighbor))
    return None


class Navigation:
    def __init__(self, app):
        self.app = app
        self.routes = WorldRoutes(app.data.tables)
        self.destination = None
        self.path = []
        self.planned_map = None
        self.exit_object = None

    def stop(self):
        self.destination, self.path, self.exit_object = None, [], None

    def go_shop(self, shop_type):
        target = self.routes.nearest_shop(self.app.map_id, shop_type)
        if target is None:
            raise ValueError('当前地图没有可解析的原版指引路线。')
        self.destination, self.planned_map, self.path = target, None, []
        self.app.keys.clear()

    def plan(self):
        app = self.app
        route = self.routes.route(app.map_id, self.destination)
        if route == ():
            self.stop()
            return
        if not route:
            self.stop()
            raise ValueError('原版出口图中没有通向目标的路线。')
        leave = str(route[0][1])
        obj = next((o for o in app.map.objects if o['group'] == 'spriteLayer'
                    and o.get('name') == leave and not o.get('gid')), None)
        if obj is None:
            self.stop()
            raise ValueError('原版地图缺少路线中的出口对象。')
        self.path = tile_path(app.map, (app.x, app.y), object_center(obj, app.map.tw, app.map.th),
                              Mounts(app.state))
        if self.path is None:
            self.stop()
            raise ValueError('当前坐骑或地形无法走到指引出口。')
        self.exit_object, self.planned_map = obj, app.map_id

    def advance(self, seconds):
        app = self.app
        if self.destination is None:
            return
        if app.keys & {'up', 'down', 'left', 'right', 'w', 'a', 's', 'd'}:
            self.stop()
            return
        if app.runtime.running or app.ui_open or app.battle or app.runtime_error:
            return
        if self.planned_map != app.map_id:
            self.plan()
        if self.destination is None:
            return
        distance = app.movement_speed()*seconds
        while self.path and distance > 0:
            x, y = self.path[0]
            dx, dy = x-app.x, y-app.y
            span = math.hypot(dx, dy)
            if span < 1e-6:
                self.path.pop(0)
                continue
            fraction = min(1, distance/span)
            before = (app.x, app.y)
            app.move_to(app.x+dx*fraction, app.y+dy*fraction)
            if before == (app.x, app.y):
                self.stop()
                raise ValueError('指引路径被当前地形阻挡。')
            app.face = ('standleft' if dx < 0 else 'standright') if abs(dx) > abs(dy) else (
                'standup' if dy < 0 else 'standdown')
            distance -= span*fraction
            if fraction >= 1:
                self.path.pop(0)
        if not self.path:
            app.try_exit()

    def guide_object(self):
        app = self.app
        target = main_task_target(app.state, app.map_id)
        if target is None:
            return None
        category, identifier, destination = target
        if destination == app.map_id:
            group = 'eventLayer' if category == 'area' else 'spriteLayer'
            return next((o for o in app.map.objects if o['group'] == group
                         and o.get('name') == str(identifier)), None)
        route = self.routes.route(app.map_id, destination)
        if not route:
            return None
        return next((o for o in app.map.objects if o['group'] == 'spriteLayer'
                     and o.get('name') == str(route[0][1]) and not o.get('gid')), None)

    def draw_guide(self, frame):
        app = self.app
        target = self.guide_object()
        if target is None:
            return
        tx, ty = object_center(target, app.map.tw, app.map.th)
        dx, dy = tx-app.x, ty-app.y
        if abs(dx) > abs(dy):
            vx, vy = (-1, 0) if dx < 0 else (1, 0)
        else:
            vx, vy = (0, -1) if dy < 0 else (0, 1)
        angle = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}[(vx, vy)]
        phase = time.monotonic() % 1.0
        bob = 17*(phase*2 if phase < .5 else (1-phase)*2)
        image = app.data.image('res/UI/guideIcon.png').rotate(angle, expand=True)
        image = image.resize((max(1, round(image.width*app.SCALE)),
                              max(1, round(image.height*app.SCALE))))
        camx, camy = app.camera_origin(app.camera_focus or (app.x, app.y))
        x = (app.x+vx*(app.map.tw*2+bob))*app.SCALE-camx
        y = (app.y+vy*(app.map.th*2+bob))*app.SCALE-camy
        frame.alpha_composite(image, (round(x-image.width/2), round(y-image.height/2)))
