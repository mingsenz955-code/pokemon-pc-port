"""Native software setup-pose renderer for original Spine 2.1 region/mesh attachments.

Animation timelines and FFD are sampled by spine_animation; IK remains pending.
This composes the original weighted meshes, instead of displaying texture atlases.
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


@lru_cache(maxsize=64)
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
    for key, region in regions.items():
        if not region['page'] or 'xy' not in region or 'size' not in region:
            continue
        with Image.open(region['page']) as image:
            x, y = map(int, region['xy'].split(','))
            w, h = map(int, region['size'].split(','))
            rotated = region.get('rotate') == 'true'
            tile = image.convert('RGBA').crop((x, y, x+(h if rotated else w), y+(w if rotated else h)))
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


@lru_cache(maxsize=64)
def load_skeleton(path_string):
    return json.loads(Path(path_string).read_text(encoding='utf-8'))


@lru_cache(maxsize=128)
def render_frame(path_string, limit=550, animation='', frame_number=0, loop=True):
    path = Path(path_string)
    data = load_skeleton(path_string)
    if animation:
        from spine_animation import sample_pose
        data = sample_pose(data, animation, frame_number/20, loop)
    textures = atlas_regions(path.with_suffix('.atlas'))
    bones, by_name = [], {}
    for row in data['bones']:
        m = matrix(row)
        if row.get('parent') in by_name:
            m = multiply(by_name[row['parent']], m)
        bones.append(m)
        by_name[row['name']] = m
    skin = data['skins'].get('default', next(iter(data['skins'].values())))
    meshes = []
    for slot in data.get('slots', []):
        name = slot.get('attachment')
        if not name:
            continue
        attachment = skin.get(slot['name'], {}).get(name)
        if not attachment:
            continue
        texture = textures.get(attachment.get('path', name))
        if texture is None:
            continue
        color = slot.get('color', 'ffffffff')
        if color != 'ffffffff':
            tint = Image.new('RGBA', texture.size, tuple(int(color[i:i+2], 16) for i in range(0, 8, 2)))
            texture = ImageChops.multiply(texture, tint)
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
    reference = render_frame(path_string, limit)[1] if animation else (left, bottom, right, top)
    scale = min(1, limit/max(reference[2]-reference[0], reference[3]-reference[1], 1))
    output = Image.new('RGBA', (max(1, math.ceil((right-left)*scale)+4),
                               max(1, math.ceil((top-bottom)*scale)+4)))
    for texture, vertices, uv, triangles in meshes:
        points = [((x-left)*scale+2, (top-y)*scale+2) for x, y in vertices]
        for index in range(0, len(triangles), 3):
            ids = triangles[index:index+3]
            paint_triangle(output, texture, [points[i] for i in ids], [uv[i] for i in ids])
    return output, (left, bottom, right, top), scale


def render_setup(path_string, limit=550):
    return render_frame(path_string, limit)[0]


def animated_frame(path_string, animation, seconds, loop=True, limit=550):
    image, bounds, scale = render_frame(path_string, limit, animation, int(max(0, seconds)*20), loop)
    _, setup, _ = render_frame(path_string, limit)
    center = ((setup[0]+setup[2])/2, (setup[1]+setup[3])/2)
    offset = ((bounds[0]-center[0])*scale-2, (center[1]-bounds[3])*scale-2)
    return image, offset, max(1, (setup[3]-setup[1])*scale+4)
