"""Original map-configured NPC patrols, independent of plot completion callbacks.

setMoveArea 0x2e09a8 / setMoveState 0x2e0954: wait 3..7 one-second
ticks, choose an original area tile, walk with search limit 30, then wait again.
"""
import random
from story_motion import StoryMotion
from event_runtime import PendingMechanic


class NpcMotion:
    def __init__(self, app, seed=None):
        self.app, self.rng = app, random.Random(seed)
        self.motion = StoryMotion(app, plot_owned=False)
        self.controllers = {}
        self.map_id = None
        self.paused = False

    def reset(self):
        app = self.app
        self.map_id = app.map_id
        self.motion.actions = []
        self.motion.faces = app.story_motion.faces
        self.controllers = {}
        for obj in getattr(app.map, 'objects', []):
            if obj['group'] != 'spriteLayer' or not obj.get('gid'):
                continue
            area = int(obj.get('props', {}).get('move', 0))
            if area > 0:
                self.controllers[str(obj['name'])] = {'area': area, 'wait': self.rng.randint(3, 7), 'clock': 0.0}

    def visible(self, identifier):
        app = self.app
        obj = next(o for o in app.map.objects if o['group'] == 'spriteLayer'
                   and o.get('gid') and str(o.get('name')) == identifier)
        return bool(app.state.visible.get(self.motion.key(2, identifier),
                                         int(obj.get('props', {}).get('state', 1))))

    def advance(self, seconds):
        app = self.app
        if self.map_id != app.map_id:
            self.reset()
        self.motion.faces = app.story_motion.faces
        if app.runtime.running or app.battle:
            if not self.paused:
                self.motion.actions = []
                for controller in self.controllers.values():
                    controller.update(wait=self.rng.randint(3, 7), clock=0.0)
            self.paused = True
            return
        self.paused = False
        before = {str(action['id']) for action in self.motion.actions}
        self.motion.advance(seconds)
        moving = {str(action['id']) for action in self.motion.actions}
        for identifier in before-moving:
            self.controllers[identifier].update(wait=self.rng.randint(3, 7), clock=0.0)
        for identifier, controller in self.controllers.items():
            if identifier in before or not self.visible(identifier):
                continue
            controller['clock'] += max(0, seconds)
            while controller['clock'] >= 1 and controller['wait'] > 0:
                controller['clock'] -= 1
                controller['wait'] -= 1
            if controller['wait'] > 0:
                continue
            area = next((o for o in app.map.objects if o['group'] == 'eventLayer'
                         and str(o.get('name')) == str(controller['area'])), None)
            if area is None:
                controller.update(wait=self.rng.randint(3, 7), clock=0.0)
                continue
            # getRandomPosition @ 0x2d5df4: truncate min+r*(max-min-1).
            x = int(float(area['x'])/app.map.tw + self.rng.random()*max(0, float(area.get('width', 64))/app.map.tw-1))
            y = int(float(area['y'])/app.map.th + self.rng.random()*max(0, float(area.get('height', 64))/app.map.th-1))
            previous = self.motion.actions
            try:
                self.motion.begin([{'spritetype': 2, 'spriteid': int(identifier),
                                    'x': x, 'y': y, 'speedscale': 1, 'face': 0}], path_limit=30)
                new_actions = self.motion.actions
            except (PendingMechanic, ValueError, KeyError) as error:
                new_actions = []
                app.state.audit.append({'npc_patrol': identifier, 'pending': str(error)})
            finally:
                self.motion.actions = previous
            self.motion.actions.extend(new_actions)
            if not new_actions:
                controller.update(wait=self.rng.randint(3, 7), clock=0.0)

    def snapshot(self):
        return {'map': self.map_id, 'controllers': self.controllers,
                'actions': self.motion.actions, 'random_state': self.rng.getstate()}

    def restore(self, snapshot):
        if not snapshot or int(snapshot.get('map', -1)) != self.app.map_id:
            return
        def tuples(value):
            return tuple(tuples(v) for v in value) if isinstance(value, list) else value
        self.controllers = snapshot['controllers']
        self.motion.actions = snapshot['actions']
        self.rng.setstate(tuples(snapshot['random_state']))
