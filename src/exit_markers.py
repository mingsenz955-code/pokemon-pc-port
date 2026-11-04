"""VillageExitControler arrows using the recovered jiantou animation."""
from functools import lru_cache
from PIL import Image


def exit_markers(world):
    faces = {1: 'standup', 2: 'standdown', 3: 'standleft', 4: 'standright'}
    for obj in world.objects:
        props = obj.get('props', {})
        if obj.get('group') != 'spriteLayer' or not props.get('toExit'):
            continue
        face = faces.get(int(props.get('face', 0)))
        if not face:
            continue
        w, h = float(obj.get('width', world.tw)), float(obj.get('height', world.th))
        horizontal = face in ('standup', 'standdown')
        spacing = 2*(world.tw if horizontal else world.th)
        count = max(1, int((w if horizontal else h)//spacing))
        for i in range(count):
            offset = (i-(count-1)/2)*spacing
            yield (float(obj['x'])+w/2+(offset if horizontal else 0),
                   float(obj['y'])+h/2+(0 if horizontal else offset), face)


class ExitMarkers:
    @lru_cache(maxsize=144)
    def exit_arrow_frame(self, face, frame):
        source = self.data.village_sprite('40001', face, frame)
        if source is None:
            return None
        origin = source.info.get('origin', (source.width/2, source.height/2))
        image = source.resize((max(1, round(source.width*self.SCALE)),
                               max(1, round(source.height*self.SCALE))), Image.Resampling.LANCZOS)
        return image, (origin[0]*self.SCALE, origin[1]*self.SCALE)

    def draw_exit_markers(self, frame):
        cx, cy = self.camera_origin()
        for x, y, face in exit_markers(self.map):
            sx, sy = x*self.SCALE-cx, y*self.SCALE-cy
            if not (-120 < sx < self.WIDTH+120 and -120 < sy < self.HEIGHT+120):
                continue
            pose = self.exit_arrow_frame(face, int(self.scene_animation_time*60) % (36 if face in ('standleft', 'standright') else 35))
            if pose:
                image, origin = pose
                frame.alpha_composite(image, (round(sx-origin[0]), round(sy-origin[1])))
