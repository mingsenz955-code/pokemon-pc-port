"""Direction marker for a user-started, walkable task-navigation route.

The previous always-on early-story hint is not the requested button-triggered
navigation. The marker now shares the actual route followed by Guide.
"""
from PIL import Image


class TaskGuide:
    def __init__(self, app):
        self.app = app
        self.direction = None
        self.started = 0.0

    def point(self):
        # This is the explicitly requested navigation route, not the separate
        # early-story hint created automatically by createMainTaskGuideIcon.
        guide = self.app.guide
        if not guide.active or guide.click_mode or not guide.waypoints:
            return None
        # Point down the currently walkable route, never through a wall at the
        # remote NPC. Stop the look-ahead at the first turn.
        previous = (self.app.x, self.app.y)
        direction = None
        result = None
        for point in guide.waypoints:
            dx, dy = point[0]-previous[0], point[1]-previous[1]
            step = (0 if abs(dx) < .01 else 1 if dx > 0 else -1,
                    0 if abs(dy) < .01 else 1 if dy > 0 else -1)
            if step == (0, 0):
                continue
            if direction is not None and step != direction:
                break
            direction, result, previous = step, point, point
        return result

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
