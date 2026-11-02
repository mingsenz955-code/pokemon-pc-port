"""Software particles sampled from recovered Cocos2d plist emitter parameters."""
import base64
import io
import math
import plistlib
import random
import zlib
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageChops


@lru_cache(maxsize=16)
def emitter(path_string):
    path = Path(path_string)
    data = plistlib.loads(path.read_bytes())
    encoded = data.get('textureImageData')
    if encoded:
        raw = base64.b64decode(encoded)
        texture = Image.open(io.BytesIO(zlib.decompress(raw, 15+32))).convert('RGBA')
    else:
        texture = Image.open(path.parent/str(data['textureFileName'])).convert('RGBA')
    return data, texture


def draw_emitter(frame, path, position, scale, elapsed, alpha=1, clip=None):
    data, texture = emitter(str(path))
    def val(key, default=0):
        return float(data.get(key, default))
    life = max(.01, val('particleLifespan', 1))
    count = max(1, int(val('maxParticles', 30)))
    rate = count/life
    duration = val('duration', -1)
    elapsed = max(0, float(elapsed))
    start = max(0, int((elapsed-life-abs(val('particleLifespanVariance')))*rate))
    end = int(elapsed*rate)
    layer = Image.new('RGBA', frame.size)
    for index in range(start, end+1):
        born = index/rate
        if duration >= 0 and born > duration:
            continue
        rng = random.Random(index+10372367)
        def varied(name, variance=None, default=0):
            return val(name, default)+rng.uniform(-1, 1)*val(variance or name+'Variance')
        lifetime = max(.01, varied('particleLifespan'))
        age = elapsed-born
        if age < 0 or age >= lifetime:
            continue
        percent = age/lifetime
        x, y = varied('sourcePositionx', 'sourcePositionVariancex'), varied('sourcePositiony', 'sourcePositionVariancey')
        angle = math.radians(varied('angle'))
        if int(val('emitterType')) == 1:
            radius_a, radius_b = varied('maxRadius'), varied('minRadius')
            radius = radius_a+(radius_b-radius_a)*percent
            angle += math.radians(varied('rotatePerSecond'))*age
            x -= math.cos(angle)*radius
            y -= math.sin(angle)*radius
        else:
            speed = varied('speed')
            vx, vy = math.cos(angle)*speed, math.sin(angle)*speed
            radial, tangent = varied('radialAcceleration', 'radialAccelVariance'), varied('tangentialAcceleration', 'tangentialAccelVariance')
            remaining = age
            while remaining > 1e-6:
                step = min(1/60, remaining)
                length = math.hypot(x, y)
                nx, ny = (x/length, y/length) if length > 1e-6 else (0, 0)
                vx += (val('gravityx')+nx*radial-ny*tangent)*step
                vy += (val('gravityy')+ny*radial+nx*tangent)*step
                x, y = x+vx*step, y+vy*step
                remaining -= step
        initial = max(0, varied('startParticleSize'))
        finish = varied('finishParticleSize')
        size = initial if finish < 0 else initial+(max(0, finish)-initial)*percent
        rgba = []
        for key in ('Red', 'Green', 'Blue', 'Alpha'):
            a = varied('startColor'+key, 'startColorVariance'+key, 1)
            b = varied('finishColor'+key, 'finishColorVariance'+key, 1)
            rgba.append(max(0, min(1, a+(b-a)*percent))*(alpha if key == 'Alpha' else 1))
        tile = Image.merge('RGBA', tuple(c.point(lambda p, f=factor: round(p*f))
                                       for c, factor in zip(texture.split(), rgba)))
        tile = tile.resize((max(1, round(size*abs(scale[0]))), max(1, round(size*abs(scale[1])))), Image.Resampling.BILINEAR)
        start_rotation, end_rotation = varied('rotationStart'), varied('rotationEnd')
        rotation = start_rotation+(end_rotation-start_rotation)*percent
        if rotation:
            tile = tile.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)
        layer.alpha_composite(tile, (round(position[0]+x*scale[0]-tile.width/2),
                                     round(position[1]-y*scale[1]-tile.height/2)))
    if clip:
        x, y, r, b = map(round, clip)
        cropped = Image.new('RGBA', frame.size)
        cropped.alpha_composite(layer.crop((x, y, r, b)), (x, y))
        layer = cropped
    if int(val('blendFuncDestination', 771)) == 1:
        # Particle textures are premultiplied for ONE/ONE additive blending.
        colored = ImageChops.multiply(layer.convert('RGB'), Image.merge('RGB', (layer.getchannel('A'),)*3))
        merged = ImageChops.add(frame.convert('RGB'), colored)
        frame.paste(Image.merge('RGBA', (*merged.split(), ImageChops.lighter(frame.getchannel('A'), layer.getchannel('A')))))
    else:
        frame.alpha_composite(layer)
