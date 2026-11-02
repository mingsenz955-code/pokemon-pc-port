"""Original early-main-task direction icon, independent of click navigation.

createMainTaskGuideIcon 0x2dfecc limits the guide to MainTask key <= 17.
mainTaskGuideIconUpdate 0x2e1274 chooses the dominant axis and runs two
0.5-second MoveBy actions of +/-17, two map tiles away from the player.
"""
from PIL import Image
from guide import GuideResolver


class TaskGuide:
    def __init__(self, app):
        self.app = app
        self.signature = None
        self.target = None
        self.direction = None
        self.started = 0.0

    def point(self):
        app, state = self.app, self.app.state
        if state.main_task > 17 or state.main_state not in (3, 4):
            return None
        stamp = (id(state), state.main_task, state.main_state, app.map_id)
        if stamp != self.signature:
            self.signature = stamp
            row = state.tables['MainTask'].get(str(state.main_task))
            self.target = None
            if row:
                kind = int(row['conditionType'])
                if (kind == 1 and state.main_state != 3) or (kind == 2 and state.main_state != 4):
                    return None
                self.target = GuideResolver(app.data, state).from_task('main', str(state.main_task), row, state.main_state)
        target = self.target
        if not target or not target.map_id:
            return None
        if target.map_id != app.map_id:
            route = app.guide.graph.route(app.map_id, target.map_id)
            if len(route) < 2:
                return None
            edge = app.guide.graph.edge(route[0], route[1])
            obj = next((o for o in app.map.objects if o['group'] == 'spriteLayer'
                        and str(o.get('name')) == edge['from_exit']), None)
            if obj:
                return float(obj['x'])+float(obj.get('width', 64))/2, float(obj['y'])+float(obj.get('height', 64))/2
            return None
        if target.kind in ('map', 'catch', 'exit'):
            return None
        if target.kind == 'npc':
            actors = [a for a in app.actors() if str(a[0]) == target.npc_id
                      and str(a[1]).isdigit() and 20000 <= int(a[1]) < 30000]
            if actors:
                return actors[-1][2:]
            return None
        return target.x, target.y

    def pose(self):
        point = self.point()
        if point is None:
            return None
        app = self.app
        dx, dy = point[0]-app.x, point[1]-app.y
        if dx == dy == 0:
            direction = app.face
        elif abs(dx) > abs(dy):
            direction = 'standleft' if dx < 0 else 'standright'
        else:
            direction = 'standup' if dy < 0 else 'standdown'
        now = getattr(app, 'scene_animation_time', 0)
        if direction != self.direction:
            self.direction, self.started = direction, now
        phase = ((now-self.started) % 1.0)*2
        pulse = 17*(phase if phase <= 1 else 2-phase)
        vx, vy, rotation = {'standup': (0, -1, 90), 'standdown': (0, 1, -90),
                            'standleft': (-1, 0, 180), 'standright': (1, 0, 0)}[direction]
        return app.x+vx*(app.map.tw*2+pulse), app.y+vy*(app.map.th*2+pulse), rotation

    def draw(self, frame):
        app = self.app
        if app.runtime.running or app.battle or not app.main_ui_visible or not app.player_visible:
            return
        pose = self.pose()
        if pose is None:
            return
        x, y, angle = pose
        image = app.data.image('res/UI/guideIcon.png').rotate(angle, expand=True)
        image = image.resize((max(1, round(image.width*app.SCALE)), max(1, round(image.height*app.SCALE))), Image.Resampling.LANCZOS)
        cx, cy = app.camera_origin()
        frame.alpha_composite(image, (round(x*app.SCALE-cx-image.width/2), round(y*app.SCALE-cy-image.height/2)))
