"""Native story walking from original ToPlace / spriteMoveToPosition rules.

ARM: wrapper 0x2dc03e; A* 0x2e6944; neighbour order 0x2da6a2;
walkAction 0x2e6210. Dynamic multi-tile collider/exit semantics remain audited
separately; unreachable goals use the original closest-H candidate path.
"""
import heapq
import math

from event_runtime import PendingMechanic
from mounts import Mounts

FACES = {1: 'standup', 2: 'standdown', 3: 'standleft', 4: 'standright'}


def destination(parameter, player, player_face, tile_size):
    """Return top-origin map position; pspace 1/2 are relative to PLAYER."""
    tw, th = tile_size
    x, y = float(parameter['x']), float(parameter['y'])
    space = int(parameter.get('pspace', 0))
    face = int(parameter.get('face', 0))
    if space in (1, 2):
        if space == 2:
            direction = face or next((k for k, v in FACES.items() if v == player_face), 0)
            x, y = {1: (x, y), 2: (-x, -y), 3: (y, -x), 4: (y, x)}.get(direction, (0, 0))
        x, y = math.floor(player[0]/tw)+x, math.floor(player[1]/th)+y
    elif space != 0:
        raise PendingMechanic(f'未知原版剧情坐标空间 {space}')
    return [(x+.5)*tw, (y+.5)*th]


def shortest_path(world, start, goal, blocked):
    """Original cardinal A*: step cost 10, Manhattan H, newer equal-F first."""
    source = (int(start[0]//world.tw), int(start[1]//world.th))
    target = (int(goal[0]//world.tw), int(goal[1]//world.th))
    def valid(tile):
        return 0 <= tile[0] < world.width and 0 <= tile[1] < world.height
    if not valid(source):
        return None
    if source == target:
        return []
    frontier, costs, parents, closed = [(0, 0, source)], {source: 0}, {source: None}, set()
    sequence = 0
    closest, closest_h = None, math.inf
    def reconstruct(current):
        path = []
        while current != source:
            path.append([(current[0]+.5)*world.tw, (current[1]+.5)*world.th])
            current = parents[current]
        return list(reversed(path))
    while frontier:
        priority, _, current = heapq.heappop(frontier)
        if current in closed:
            continue
        closed.add(current)
        if current == target:
            return reconstruct(current)
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            neighbor = (current[0]+dx, current[1]+dy)
            if neighbor in closed or not valid(neighbor) or blocked(*neighbor):
                continue
            cost = costs[current]+10
            if cost >= costs.get(neighbor, math.inf):
                continue
            costs[neighbor], parents[neighbor] = cost, current
            sequence += 1
            h = abs(neighbor[0]-target[0])+abs(neighbor[1]-target[1])
            # insertInOpenSteps @ 0x2e6630 retains the first inserted
            # parented node with the smallest H; equal H does not replace it.
            if h < closest_h:
                closest, closest_h = neighbor, h
            heapq.heappush(frontier, (cost+h, -sequence, neighbor))
    return reconstruct(closest) if closest is not None else []


class StoryMotion:
    def __init__(self, app):
        self.app = app
        self.actions = []
        self.faces = {}

    def key(self, kind, identifier):
        return f'{self.app.map_id}:{int(kind)}:{identifier}'

    def position(self, kind, identifier):
        app = self.app
        if kind == 1:
            return [app.x, app.y]
        if kind == 7:
            row = app.state.temp_npcs.get(str(identifier))
            if row and int(row['map']) == app.map_id:
                return [row['x'], row['y']]
        elif kind == 2:
            key = self.key(kind, identifier)
            if key in app.state.positions:
                return list(app.state.positions[key])
            obj = next((o for o in app.map.objects if o['group'] == 'spriteLayer'
                        and o.get('gid') and str(o.get('name')) == str(identifier)), None)
            if obj:
                return [float(obj['x'])+app.map.tw/2, float(obj['y'])]
        raise PendingMechanic(f'当前原版地图没有人物 {kind}:{identifier}')

    def set_position(self, action, point):
        app = self.app
        kind, identifier = action['kind'], action['id']
        if kind == 1:
            app.x, app.y = point
        elif kind == 7:
            row = app.state.temp_npcs[str(identifier)]
            row['x'], row['y'] = point
        else:
            app.state.positions[self.key(kind, identifier)] = list(point)

    def set_face(self, kind, identifier, face):
        if face not in FACES:
            return
        self.faces[self.key(kind, identifier)] = FACES[face]
        if kind == 1:
            self.app.face = FACES[face]

    def blocked(self, kind, identifier):
        app, world = self.app, self.app.map
        mounts = Mounts(app.state) if kind == 1 else None
        occupied = set()
        # isNpcAtTileCoord @ 0x2d8dd2 explicitly exempts SpriteType 2.
        for oid, sid, x, y in app.actors():
            if str(oid) in (str(identifier), 'temp:'+str(identifier)):
                continue
            if kind == 2 and str(sid) != '30001':
                continue
            occupied.add((int(x//world.tw), int(y//world.th)))
        return lambda tx, ty: ((tx, ty) in occupied or
            world.blocked((tx+.5)*world.tw, (ty+.5)*world.th, mounts))

    def begin(self, rows):
        app = self.app
        self.actions = []
        seen = set()
        for parameter in rows:
            kind, identifier = int(parameter.get('spritetype', 2)), int(parameter.get('spriteid', 0))
            key = self.key(kind, identifier)
            if key in seen:
                raise PendingMechanic('同一剧情指令重复指定人物，需要核对原版覆盖回调')
            seen.add(key)
            start = self.position(kind, identifier)
            if kind == 1:
                app.process_player_areas(force=True)
            target = destination(parameter, (app.x, app.y), app.face, (app.map.tw, app.map.th))
            speed = int(parameter.get('speedscale', 1))
            if speed < 0:
                raise ValueError('剧情人物 speedscale 不能小于零')
            action = {'kind': kind, 'id': identifier, 'map': app.map_id,
                      'speed': speed, 'end_face': int(parameter.get('face', 0)),
                      'age': 0.0, 'path': [], 'segment': None}
            if speed == 0:
                self.set_position(action, target)
                self.set_face(kind, identifier, action['end_face'])
                continue
            path = shortest_path(app.map, start, target, self.blocked(kind, identifier))
            if path is None:
                raise PendingMechanic(f'人物 {kind}:{identifier} 无法沿原地形走到剧情目标，未直接传送')
            if not path:
                self.set_face(kind, identifier, action['end_face'])
                continue
            action['path'] = path
            self.actions.append(action)

    def animation(self, kind, identifier, fallback):
        action = next((a for a in self.actions if a['kind'] == kind and str(a['id']) == str(identifier)), None)
        face = self.faces.get(self.key(kind, identifier), fallback)
        return face.replace('stand', 'walk') if action else face

    def advance(self, seconds):
        app = self.app
        if not self.actions:
            return
        for action in list(self.actions):
            if action['map'] != app.map_id:
                raise PendingMechanic('剧情人物尚未到达时地图被替换，未伪造完成回调')
            remaining = max(0, seconds)
            action['age'] += remaining
            while remaining > 0 and action['path']:
                segment = action['segment']
                if segment is None:
                    start = self.position(action['kind'], action['id'])
                    target = action['path'][0]
                    dx, dy = target[0]-start[0], target[1]-start[1]
                    face = (3 if dx < 0 else 4) if abs(dx) > abs(dy) else (1 if dy < 0 else 2)
                    self.set_face(action['kind'], action['id'], face)
                    base = app.map.tw/.2
                    if action['kind'] == 1:
                        Mounts(app.state).enter(app.map.terrain_at(*target), int(app.map.info['mapType']))
                        base = app.movement_speed()
                    duration = math.dist(start, target)/base/action['speed']
                    segment = {'start': start, 'target': target, 'duration': duration, 'elapsed': 0.0}
                    action['segment'] = segment
                used = min(remaining, max(0, segment['duration']-segment['elapsed']))
                segment['elapsed'] += used
                remaining -= used
                fraction = min(1, segment['elapsed']/segment['duration']) if segment['duration'] else 1
                self.set_position(action, [a+(b-a)*fraction for a, b in zip(segment['start'], segment['target'])])
                if fraction >= 1:
                    action['path'].pop(0)
                    action['segment'] = None
                    if action['kind'] == 1:
                        app.process_player_areas(force=True)
                else:
                    break
            if not action['path']:
                self.set_face(action['kind'], action['id'], action['end_face'])
                self.actions.remove(action)
        if not self.actions and app.runtime.pending and app.runtime.pending.kind == 'toplace':
            app.runtime.resume()
