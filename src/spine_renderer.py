"""Spine 2.1 region/mesh rendering with bone/slot/draw-order timelines.

FFD, IK and animation mixing remain unimplemented.
"""
import json
import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


def multiply(a, b):
    return (a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1],
            a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5])


def transform(matrix, x, y):
    a, b, c, d, tx, ty = matrix
    return a*x+c*y+tx, b*x+d*y+ty


def matrix(row):
    angle = math.radians(row.get('rotation', 0))
    sx, sy = row.get('scaleX', 1), row.get('scaleY', 1)
    return (math.cos(angle)*sx, math.sin(angle)*sx, -math.sin(angle)*sy,
            math.cos(angle)*sy, row.get('x', 0), row.get('y', 0))


@lru_cache(maxsize=12)
def atlas_regions(path):
    lines = path.read_text(encoding='utf-8').splitlines()
    page, name, regions = None, None, {}
    for line in lines:
        if not line.strip():
            name = None
            continue
        if not line.startswith((' ', '\t')) and ':' not in line:
            if (path.parent/line).is_file() and line.endswith('.png'):
                page, name = path.parent/line, None
            else:
                name = line.strip()
                regions[name] = {'page': page}
        elif name and ':' in line:
            key, value = [s.strip() for s in line.split(':', 1)]
            regions[name][key] = value
    result = {}
    pages = {}
    for key, region in regions.items():
        if not region['page'] or 'xy' not in region or 'size' not in region:
            continue
        page = region['page']
        if page not in pages:
            with Image.open(page) as image:
                pages[page] = image.convert('RGBA')
        x, y = map(int, region['xy'].split(','))
        w, h = map(int, region['size'].split(','))
        rotated = region.get('rotate') == 'true'
        tile = pages[page].crop((x, y, x+(h if rotated else w), y+(w if rotated else h)))
        if rotated:
            tile = tile.transpose(Image.Transpose.ROTATE_270)
        result[key] = tile
    return result


def paint_triangle(destination, texture, points, uv):
    minx, miny = math.floor(min(p[0] for p in points)), math.floor(min(p[1] for p in points))
    maxx, maxy = math.ceil(max(p[0] for p in points)), math.ceil(max(p[1] for p in points))
    if maxx <= minx or maxy <= miny:
        return
    (x0, y0), (x1, y1), (x2, y2) = points
    determinant = (x1-x0)*(y2-y0)-(x2-x0)*(y1-y0)
    if abs(determinant) < 1e-7:
        return
    def coefficients(values):
        v0, v1, v2 = values
        a = ((v1-v0)*(y2-y0)-(v2-v0)*(y1-y0))/determinant
        b = ((x1-x0)*(v2-v0)-(x2-x0)*(v1-v0))/determinant
        return a, b, v0-a*x0-b*y0+a*minx+b*miny
    affine = coefficients([v[0] for v in uv])+coefficients([v[1] for v in uv])
    patch = texture.transform((maxx-minx, maxy-miny), Image.Transform.AFFINE, affine,
                              resample=Image.Resampling.BICUBIC)
    mask = Image.new('L', patch.size)
    ImageDraw.Draw(mask).polygon([(x-minx, y-miny) for x, y in points], fill=255)
    patch.putalpha(ImageChops.multiply(mask, patch.getchannel('A')))
    destination.alpha_composite(patch, (minx, miny))


@lru_cache(maxsize=32)
def skeleton(path_string):
    return json.loads(Path(path_string).read_text(encoding='utf-8'))


def animation_duration(clip):
    def times(value):
        if isinstance(value, dict):
            yield float(value.get('time', 0))
            for child in value.values():
                yield from times(child)
        elif isinstance(value, list):
            for child in value:
                yield from times(child)
    return max(times(clip), default=0)


def curve_percent(curve, percent):
    if curve == 'stepped':
        return 0
    if not isinstance(curve, list) or len(curve) != 4:
        return percent
    x1, y1, x2, y2 = curve
    def bezier(t, a, b):
        return 3*(1-t)**2*t*a+3*(1-t)*t*t*b+t*t*t
    low, high = 0.0, 1.0
    for _ in range(16):
        mid = (low+high)/2
        if bezier(mid, x1, x2) < percent:
            low = mid
        else:
            high = mid
    return bezier((low+high)/2, y1, y2)


def timeline(frames, seconds, fields, defaults, rotation=False):
    if not frames or seconds < float(frames[0].get('time', 0)):
        return None
    index = max(i for i, f in enumerate(frames) if float(f.get('time', 0)) <= seconds)
    left = frames[index]
    start = [float(left.get(k, d)) for k, d in zip(fields, defaults)]
    if index == len(frames)-1:
        return start
    right = frames[index+1]
    span = float(right.get('time', 0))-float(left.get('time', 0))
    pct = curve_percent(left.get('curve'), (seconds-float(left.get('time', 0)))/span if span else 0)
    result = []
    for key, default, a in zip(fields, defaults, start):
        delta = float(right.get(key, default))-a
        if rotation:
            delta = (delta+180)%360-180
        result.append(a+delta*pct)
    return result


def draw_order(slots, frames, seconds):
    frames = [f for f in frames if float(f.get('time', 0)) <= seconds]
    if not frames or not frames[-1].get('offsets'):
        return slots
    names = {s['name']: i for i, s in enumerate(slots)}
    order, unchanged, cursor = [None]*len(slots), [], 0
    for offset in frames[-1]['offsets']:
        index = names[offset['slot']]
        while cursor < index:
            unchanged.append(cursor)
            cursor += 1
        order[cursor+int(offset['offset'])] = cursor
        cursor += 1
    unchanged.extend(range(cursor, len(slots)))
    for i in range(len(slots)-1, -1, -1):
        if order[i] is None:
            order[i] = unchanged.pop()
    return [slots[i] for i in order]


@lru_cache(maxsize=96)
def render_pose(path_string, animation='', frame=0, loop=True, limit=550, fps=12):
    path = Path(path_string)
    data = skeleton(path_string)
    clip = data.get('animations', {}).get(animation, {})
    seconds, duration = float(frame)/fps, animation_duration(clip)
    if loop and duration > 0:
        seconds %= duration
    else:
        seconds = min(seconds, duration)
    textures = atlas_regions(path.with_suffix('.atlas'))
    bones, by_name = [], {}
    for row in data['bones']:
        row = dict(row)
        tracks = clip.get('bones', {}).get(row['name'], {})
        for name, fields, defaults in [('rotate', ['angle'], [0]), ('translate', ['x', 'y'], [0, 0]),
                                       ('scale', ['x', 'y'], [1, 1])]:
            values = timeline(tracks.get(name, []), seconds, fields, defaults, name == 'rotate')
            if values is None:
                continue
            for field, value in zip(fields, values):
                key = 'rotation' if name == 'rotate' else ('scale'+field.upper() if name == 'scale' else field)
                row[key] = row.get(key, 1)*value if name == 'scale' else row.get(key, 0)+value
        m = matrix(row)
        if row.get('parent') in by_name:
            m = multiply(by_name[row['parent']], m)
        bones.append(m)
        by_name[row['name']] = m
    skin = data['skins'].get('default', next(iter(data['skins'].values())))
    meshes = []
    slots = draw_order(data.get('slots', []), clip.get('drawOrder', clip.get('draworder', [])), seconds)
    for slot in slots:
        name = slot.get('attachment')
        tracks = clip.get('slots', {}).get(slot['name'], {})
        attachments = [f for f in tracks.get('attachment', []) if float(f.get('time', 0)) <= seconds]
        if attachments:
            name = attachments[-1].get('name')
        if not name:
            continue
        attachment = skin.get(slot['name'], {}).get(name)
        if not attachment:
            continue
        texture = textures.get(attachment.get('path', name))
        if texture is None:
            continue
        color_frames = tracks.get('color', [])
        rgba_frames = [dict(f, **{key: int(str(f.get('color', 'ffffffff'))[i*2:i*2+2], 16)/255
                                  for i, key in enumerate(('r', 'g', 'b', 'a'))}) for f in color_frames]
        rgba = timeline(rgba_frames, seconds, ['r', 'g', 'b', 'a'], [1]*4)
        if rgba is None:
            color = str(slot.get('color', 'ffffffff'))
            rgba = [int(color[i*2:i*2+2], 16)/255 for i in range(4)]
        if rgba != [1]*4:
            texture = Image.merge('RGBA', tuple(channel.point(lambda v, factor=f: round(v*factor))
                                   for channel, f in zip(texture.split(), rgba)))
        kind = attachment.get('type', 'region')
        if kind == 'region':
            width, height = attachment.get('width', texture.width), attachment.get('height', texture.height)
            m = multiply(by_name[slot['bone']], matrix(attachment))
            vertices = [transform(m, x, y) for x, y in [(-width/2, height/2), (width/2, height/2),
                                                        (width/2, -height/2), (-width/2, -height/2)]]
            uvs, triangles = [(0, 0), (texture.width, 0), (texture.width, texture.height), (0, texture.height)], [0, 1, 2, 0, 2, 3]
        elif kind in ['mesh', 'skinnedmesh', 'weightedmesh']:
            raw, vertices = attachment['vertices'], []
            if kind in ['skinnedmesh', 'weightedmesh']:
                cursor = 0
                while cursor < len(raw):
                    count = int(raw[cursor])
                    cursor += 1
                    x, y = 0, 0
                    for _ in range(count):
                        index = int(raw[cursor])
                        px, py = transform(bones[index], raw[cursor+1], raw[cursor+2])
                        weight = raw[cursor+3]
                        x, y = x+px*weight, y+py*weight
                        cursor += 4
                    vertices.append((x, y))
            else:
                vertices = [transform(by_name[slot['bone']], raw[i], raw[i+1]) for i in range(0, len(raw), 2)]
            uvs = [(attachment['uvs'][i]*texture.width, attachment['uvs'][i+1]*texture.height)
                   for i in range(0, len(attachment['uvs']), 2)]
            triangles = attachment['triangles']
        else:
            raise NotImplementedError(f'Original Spine attachment {kind}')
        meshes.append((texture, vertices, uvs, triangles))
    all_vertices = [v for _, vertices, _, _ in meshes for v in vertices]
    if not all_vertices:
        raise ValueError(f'No original region/mesh attachments in {path.name}')
    left, right = min(v[0] for v in all_vertices), max(v[0] for v in all_vertices)
    bottom, top = min(v[1] for v in all_vertices), max(v[1] for v in all_vertices)
    scale = (render_pose(path_string, limit=limit).info['pixels_per_unit'] if animation else
             min(1, limit/max(right-left, top-bottom, 1)))
    output = Image.new('RGBA', (max(1, math.ceil((right-left)*scale)+4),
                               max(1, math.ceil((top-bottom)*scale)+4)))
    for texture, vertices, uv, triangles in meshes:
        points = [((x-left)*scale+2, (top-y)*scale+2) for x, y in vertices]
        for index in range(0, len(triangles), 3):
            ids = triangles[index:index+3]
            paint_triangle(output, texture, [points[i] for i in ids], [uv[i] for i in ids])
    output.info['origin'] = (-left*scale+2, top*scale+2)
    output.info['pixels_per_unit'] = scale
    output.info['bone_points'] = {name: (m[4]*scale, -m[5]*scale) for name, m in by_name.items()}
    return output


def render_setup(path_string, limit=550):
    return render_pose(path_string, limit=limit)
