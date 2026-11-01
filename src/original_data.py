"""Read the recovered 1.20.4 data without substituting invented game content."""
from __future__ import annotations

import base64
import json
import math
import plistlib
import re
import struct
import xml.etree.ElementTree as ET
import zlib
from functools import lru_cache
from pathlib import Path

from PIL import Image


def props(node):
    return {p.get('name'): p.get('value', p.text or '')
            for p in node.findall('./properties/property')}


def multiply(a, b):
    return (a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1],
            a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5])


def matrix(d):
    x, y = float(d.get('kX', 0)), float(d.get('kY', 0))
    sx, sy = float(d.get('cX', 1)), float(d.get('cY', 1))
    return (math.cos(y)*sx, math.sin(y)*sx, math.sin(x)*sy,
            math.cos(x)*sy, float(d.get('x', 0)), float(d.get('y', 0)))


class OriginalData:
    def __init__(self, root):
        self.root = Path(root)
        self.assets = self.root/'assets'
        self.tables = json.loads((self.root/'tables.json').read_text(encoding='utf-8'))
        self.image_paths = {p.name: p for p in self.assets.rglob('*.png')}

    @lru_cache(maxsize=128)
    def image(self, path):
        p = self.assets/path
        if not p.exists():
            p = self.image_paths[Path(path).name]
        with Image.open(p) as im:
            return im.convert('RGBA')

    def event(self, name):
        return json.loads((self.root/'events'/name).read_text(encoding='utf-8'))

    def village_sprite(self, sid, animation='standdown'):
        row = self.tables['VillageSprite'].get(str(sid))
        if not row:
            return None
        filename = row['fileName']
        if row['fileType'] == '4':
            if animation == 'standright':
                result = self.armature(filename, 'standleft')
                return result.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if result else None
            return self.armature(filename, animation)
        if row['fileType'] == '3':
            from spine_renderer import render_setup
            path = self.assets/'Sprite/Spine'/(filename+'.json')
            if path.exists():
                im = render_setup(str(path)).copy()
                scale = float(row.get('scale', 1))
                return im.resize((max(1, round(im.width*scale)), max(1, round(im.height*scale))), Image.Resampling.LANCZOS)
            return None
        filename = filename if Path(filename).suffix else filename+'.png'
        if filename not in self.image_paths:
            return None
        im = self.image('Sprite/'+filename)
        scale = float(row.get('scale', 1))
        return im.resize((max(1, round(im.width*scale)), max(1, round(im.height*scale))), Image.Resampling.LANCZOS)

    @lru_cache(maxsize=128)
    def pet_image(self, species):
        """Original Spine setup pose for a Pet row (battle/party display)."""
        row = self.tables['Pet'].get(str(species))
        if not row:
            return None
        path = self.assets/'Sprite/Spine'/(str(row['filePath'])+'.json')
        if not path.exists():
            return None
        from spine_renderer import render_setup
        image = render_setup(str(path)).copy()
        scale = float(row.get('scale', 1) or 1)
        if scale != 1:
            image = image.resize((max(1, round(image.width*scale)),
                                  max(1, round(image.height*scale))), Image.Resampling.LANCZOS)
        return image

    @lru_cache(maxsize=64)
    def armature(self, name, animation='standdown', frame=0):
        """Software preview of Cocos Studio bones, including original texture pivots."""
        folder = self.assets/'Sprite/CcsAni'
        export = folder/f'{name}.ExportJson'
        if not export.exists():
            matches = list(self.assets.rglob(f'{name}.ExportJson'))
            if not matches:
                return None
            export = matches[0]
        folder = export.parent
        data = json.loads(export.read_text(encoding='utf-8'))
        frames = {}
        for plist in folder.glob(f'{name}[0-9]*.plist'):
            pd = plistlib.loads(plist.read_bytes())
            atlas_path = plist.with_suffix('.png')
            if not atlas_path.exists():
                continue
            atlas = Image.open(atlas_path).convert('RGBA')
            for k, v in pd.get('frames', {}).items():
                if 'x' in v:
                    x, y, w, h = (int(v[t]) for t in ['x', 'y', 'width', 'height'])
                    frames[k] = atlas.crop((x, y, x+w, y+h))
                elif 'frame' in v:
                    x, y, w, h = map(int, re.findall(r'-?\d+', v['frame']))
                    im = atlas.crop((x, y, x+(h if v.get('rotated') else w),
                                           y+(w if v.get('rotated') else h)))
                    if v.get('rotated'):
                        im = im.transpose(Image.Transpose.ROTATE_90)
                    frames[k] = im
        if not frames:
            return None
        moves = (data.get('animation_data') or [{}])[0].get('mov_data', []) or []
        move = next((m for m in moves if m['name'] == animation), moves[0] if moves else {})
        active = {}
        for bone in move.get('mov_bone_data', []) or []:
            fd = bone.get('frame_data', []) or []
            if fd:
                active[bone['name']] = max((f for f in fd if f.get('fi', 0) <= frame),
                                          key=lambda f: f.get('fi', 0), default=fd[0])
        bones = {b['name']: b for b in (data.get('armature_data') or [{'bone_data': []}])[0]['bone_data']}
        texture = {t['name']+'.png': t for t in (data.get('texture_data') or [])}
        transforms = {}

        def transform(name):
            if name in transforms:
                return transforms[name]
            b = bones[name]
            a = dict(b)
            f = active.get(name, {})
            for k in ['x', 'y', 'kX', 'kY']:
                a[k] = float(b.get(k, 0))+float(f.get(k, 0))
            for k in ['cX', 'cY']:
                a[k] = float(b.get(k, 1))*float(f.get(k, 1))
            m = matrix(a)
            if b.get('parent') in bones:
                m = multiply(transform(b['parent']), m)
            transforms[name] = m
            return m

        # Cocos texture dimensions and skeleton coordinates use content_scale differently.
        parts = []
        for name_, bone in bones.items():
            if active and name_ not in active:
                continue
            f = active.get(name_, {})
            di = int(f.get('dI', bone.get('dI', 0)))
            display = bone.get('display_data', [])
            if di < 0 or di >= len(display):
                continue
            disp = display[di]
            sprite = frames.get(disp.get('name'))
            if sprite is None:
                continue
            skin = disp.get('skin_data', [{}])[0]
            m = multiply(transform(name_), matrix(skin))
            tex = texture.get(disp['name'], {})
            tw = float(tex.get('width', sprite.width))
            th = float(tex.get('height', sprite.height))
            px, py = float(tex.get('pX', .5)), float(tex.get('pY', .5))
            m = multiply(m, (tw/sprite.width, 0, 0, -th/sprite.height, -tw*px, th*(1-py)))
            parts.append((bone.get('z', 0)+f.get('z', 0), sprite, m))
        if not parts:
            return None
        # Render in a fixed working surface and crop to the actual original silhouette.
        out = Image.new('RGBA', (640, 640))
        origin = (320, 500)
        for _, sprite, m in sorted(parts, key=lambda p: p[0]):
            a, b, c, d, tx, ty = m
            a, c, tx = a*.5, c*.5, tx*.5+origin[0]
            b, d, ty = -b*.5, -d*.5, -ty*.5+origin[1]
            det = a*d-b*c
            if abs(det) < 1e-8:
                continue
            inv = (d/det, -c/det, (c*ty-d*tx)/det,
                   -b/det, a/det, (b*tx-a*ty)/det)
            layer = sprite.transform(out.size, Image.Transform.AFFINE, inv,
                                     resample=Image.Resampling.BICUBIC)
            out.alpha_composite(layer)
        box = out.getbbox()
        return out.crop(box) if box else None

    def load_map(self, map_id):
        info = self.tables['VillageMap'][str(map_id)]
        return OriginalMap(self, info)


class OriginalMap:
    def __init__(self, data, info):
        self.data, self.info = data, info
        self.path = data.assets/'Map'/info['fileName']
        self.xml = ET.parse(self.path).getroot()
        self.width, self.height = int(self.xml.get('width')), int(self.xml.get('height'))
        self.tw, self.th = int(self.xml.get('tilewidth')), int(self.xml.get('tileheight'))
        self.layers = []
        self.tilesets = []
        self.objects = []
        for ts in self.xml.findall('tileset'):
            image = ts.find('image')
            if image is None:
                continue
            properties = {int(t.get('id')): props(t) for t in ts.findall('tile')}
            self.tilesets.append({'first': int(ts.get('firstgid')), 'name': ts.get('name'),
                                  'image': image.get('source'), 'props': properties,
                                  'tw': int(ts.get('tilewidth')), 'th': int(ts.get('tileheight'))})
        for node in self.xml.findall('layer'):
            content = node.find('data')
            encoding, compression = content.get('encoding'), content.get('compression')
            if encoding == 'base64':
                b = base64.b64decode(content.text)
                if compression == 'zlib':
                    b = zlib.decompress(b)
                vals = struct.unpack('<'+'I'*(len(b)//4), b)
            elif encoding == 'csv':
                vals = tuple(int(s.strip()) for s in content.text.split(',') if s.strip())
            else:
                vals = tuple(int(t.get('gid', 0)) for t in content.findall('tile'))
            self.layers.append((node.get('name'), vals, float(node.get('opacity', 1))))
        for group in self.xml.findall('objectgroup'):
            for node in group.findall('object'):
                self.objects.append({'group': group.get('name'), **node.attrib, 'props': props(node)})
        # 1.20.4 draws cuttable trees and breakable rocks as spriteTileLayer
        # objects carrying obsType (1=wood, 2=stone).  They are not part of
        # collideLayer, so the old terrain-only collision let the player walk
        # straight through them.
        self.obstacles = {}
        for obj in self.objects:
            if obj.get('group') != 'spriteTileLayer' or not obj.get('gid'):
                continue
            p = self.tile_properties(int(obj['gid']))
            obs = int(p.get('obsType', 0) or 0)
            if obs:
                tx = int(float(obj['x']))//self.tw
                ty = int(float(obj['y']))//self.th
                self.obstacles[(tx, ty)] = obs
        self.removed_obstacles = set()

    def tileset(self, gid):
        gid = gid & 0x1fffffff
        return next((t for t in reversed(self.tilesets) if gid >= t['first']), None)

    def tile_properties(self, gid):
        ts = self.tileset(gid)
        return ts['props'].get((gid & 0x1fffffff)-ts['first'], {}) if ts else {}

    @lru_cache(maxsize=1024)
    def tile(self, gid):
        ts = self.tileset(gid)
        if ts is None:
            return None
        # These tiles encode editor metadata; the game never draws their debug atlas.
        if any(w in ts['name'].lower() for w in ['collide', 'npc', 'exit', 'event']):
            return None
        if 'spriteId' in self.tile_properties(gid):
            return None
        if not (self.data.assets/'Map'/ts['image']).exists() and Path(ts['image']).name not in self.data.image_paths:
            return None
        image = self.data.image('Map/'+ts['image'])
        n = (gid & 0x1fffffff)-ts['first']
        columns = image.width//ts['tw']
        x, y = n % columns*ts['tw'], n//columns*ts['th']
        result = image.crop((x, y, x+ts['tw'], y+ts['th']))
        if gid & 0x20000000:
            result = result.transpose(Image.Transpose.TRANSPOSE)
        if gid & 0x80000000:
            result = result.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if gid & 0x40000000:
            result = result.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        return result

    def render(self, scale=.5, include_objects=True):
        size = self.width*self.tw, self.height*self.th
        out = Image.new('RGBA', size, (33, 51, 33, 255))
        for name, vals, opacity in self.layers:
            if 'collide' in name.lower():
                continue
            for index, gid in enumerate(vals):
                if not gid:
                    continue
                tile = self.tile(gid)
                if tile:
                    out.alpha_composite(tile, (index % self.width*self.tw,
                                               index//self.width*self.th))
        if include_objects:
            for obj in sorted(self.objects, key=lambda x: float(x.get('y', 0))):
                if obj['group'] != 'spriteTileLayer' or not obj.get('gid'):
                    continue
                tx = int(float(obj['x']))//self.tw
                ty = int(float(obj['y']))//self.th
                if (tx, ty) in self.removed_obstacles:
                    continue
                gid = int(obj['gid'])
                tile = self.tile(gid)
                p = self.tile_properties(gid)
                sid = p.get('spriteId')
                if sid in self.data.tables['VillageSprite']:
                    tile = self.data.village_sprite(sid)
                if tile:
                    out.alpha_composite(tile, (round(float(obj['x'])+self.tw/2-tile.width/2),
                                               round(float(obj['y']))-tile.height))
        return out.resize((round(size[0]*scale), round(size[1]*scale)), Image.Resampling.LANCZOS)

    def terrain_at(self, x, y):
        """Original collideTile category, or None outside the map."""
        tx, ty = int(x//self.tw), int(y//self.th)
        if not (0 <= tx < self.width and 0 <= ty < self.height):
            return None
        if (tx, ty) in getattr(self, 'obstacles', {}) and (tx, ty) not in getattr(self, 'removed_obstacles', set()):
            return self.obstacles[(tx, ty)]
        for name, vals, _ in self.layers:
            if name == 'collideLayer':
                gid = vals[ty*self.width+tx]
                return int(self.tile_properties(gid).get('collideTile', 0))
        return 0

    def obstacle_at(self, x, y):
        tx, ty = int(x//self.tw), int(y//self.th)
        return (getattr(self, 'obstacles', {}).get((tx, ty))
                if (tx, ty) not in getattr(self, 'removed_obstacles', set()) else None)

    def remove_obstacle(self, tx, ty):
        obstacles = getattr(self, 'obstacles', {})
        if (tx, ty) not in obstacles:
            return None
        self.removed_obstacles.add((tx, ty))
        return obstacles[(tx, ty)]

    def blocked(self, x, y, mounts=None):
        terrain = self.terrain_at(x, y)
        if mounts is None:
            return terrain != 0
        return not mounts.can_enter(terrain, int(self.info['mapType']))
