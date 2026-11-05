"""Read the recovered 1.20.4 data without substituting invented game content."""
from __future__ import annotations

import base64
import gzip
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
        self._repair_recovered_maps()
        from economy import adapt_tables
        adapt_tables(self.tables)
        self.image_paths = {p.name: p for p in self.assets.rglob('*.png')}

    def _repair_recovered_maps(self):
        """Recovered X map 1501 is Morpheus town, not the duplicate Moon Island row."""
        row = self.tables.get('VillageMap', {}).get('1501')
        path = self.assets/'Map/map1501.tmx'
        if not row or row.get('fileName') != 'map1201.tmx' or not path.is_file():
            return
        xml = ET.parse(path).getroot()
        exits = xml.findall(
            "./objectgroup[@name='spriteLayer']/object/properties/property[@name='toExit']/../..")
        exit_ids = sorted({node.get('name') for node in exits if not node.get('gid')})
        if {'150101', '150102', '150103', '150117'} <= set(exit_ids):
            row.update(fileName='map1501.tmx', name='墨菲斯', exitIds=','.join(exit_ids))

    @lru_cache(maxsize=1)
    def sprite_tiles(self):
        path = self.assets/'Sprite/spriteTile.json'
        if not path.exists():
            return {}
        raw = path.read_bytes()
        if not raw.lstrip().startswith(b'{'):
            alphabet = b'ABCDEFGHIJKLmnopqrstuvwxyz01234abcdefghijklMNOPQRSTUVWXYZ+/56789'
            standard = b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
            raw = base64.b64decode(raw.translate(bytes.maketrans(alphabet, standard)))
        return json.loads(raw)

    @lru_cache(maxsize=128)
    def image(self, path):
        p = self.assets/path
        if not p.exists():
            p = self.image_paths[Path(path).name]
        with Image.open(p) as im:
            return im.convert('RGBA')

    def event(self, name):
        return json.loads((self.root/'events'/name).read_text(encoding='utf-8'))

    @lru_cache(maxsize=1)
    def localized_text(self):
        rows = json.loads((self.assets/'Data/Text.json').read_text(encoding='utf-8-sig'))
        return {row['name']: row['text'] for row in rows}

    def village_sprite(self, sid, animation='standdown', frame=0):
        row = self.tables['VillageSprite'].get(str(sid))
        if not row:
            return None
        filename = row['fileName']
        if row['fileType'] == '4':
            clip = animation.replace('right', 'left')
            _, source = self.armature_source(filename)
            moves = (source.get('animation_data') or [{}])[0].get('mov_data', []) if source else []
            movement = next((m for m in moves if m['name'] == clip), {})
            if movement.get('lp') and movement.get('dr', 0) > 0:
                frame %= movement['dr']
            if animation.endswith('right'):
                return self._village_right_frame(filename, clip, frame)
            return self.armature(filename, animation, frame)
        if row['fileType'] == '3':
            return self._village_setup_frame(filename, float(row.get('scale', 1)))

        filename = filename if Path(filename).suffix else filename+'.png'
        if filename not in self.image_paths:
            return None
        im = self.image('Sprite/'+filename)
        scale = float(row.get('scale', 1))
        return im.resize((max(1, round(im.width*scale)), max(1, round(im.height*scale))), Image.Resampling.LANCZOS)

    @lru_cache(maxsize=128)
    def _village_setup_frame(self, filename, scale):
        from spine_renderer import render_setup
        path = self.spine_path(filename)
        if path is None:
            return None
        im = render_setup(str(path))
        result = im.resize((max(1, round(im.width*scale)), max(1, round(im.height*scale))), Image.Resampling.LANCZOS)
        if 'origin' in im.info:
            result.info['origin'] = tuple(v*scale for v in im.info['origin'])
        return result

    @lru_cache(maxsize=256)
    def spine_path(self, filename):
        # Native FileUtils searches both resource directories. Lasileijia is
        # shipped under Sprite itself, unlike most original pet skeletons.
        for folder in ('Sprite/Spine', 'Sprite'):
            path = self.assets/folder/(str(filename)+'.json')
            if path.is_file():
                return path
        return None

    @lru_cache(maxsize=512)
    def _village_right_frame(self, filename, clip, frame):
        result = self.armature(filename, clip, frame)
        if result is None:
            return None
        image = result.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if 'origin' in result.info:
            x, y = result.info['origin']
            image.info['origin'] = (result.width-x, y)
        return image

    @lru_cache(maxsize=128)
    def pet_image(self, species):
        """Original Spine setup pose for a Pet row (battle/party display)."""
        row = self.tables['Pet'].get(str(species))
        if not row:
            return None
        path = self.spine_path(row['filePath'])
        if path is None:
            return None
        from spine_renderer import render_setup
        image = render_setup(str(path)).copy()
        scale = float(row.get('scale', 1) or 1)
        if scale != 1:
            image = image.resize((max(1, round(image.width*scale)),
                                  max(1, round(image.height*scale))), Image.Resampling.LANCZOS)
            if 'origin' in image.info:
                image.info['origin'] = tuple(v*scale for v in image.info['origin'])
        return image

    @lru_cache(maxsize=128)
    def pet_frame(self, species, animation='stand', frame=0, loop=True, fps=12, limit=550):
        row = self.tables['Pet'][str(species)]
        path = self.spine_path(row['filePath'])
        if path is None:
            return None
        from spine_renderer import render_pose
        image = render_pose(str(path), animation, int(frame), loop, limit=limit, fps=fps).copy()
        scale = float(row.get('scale', 1) or 1)
        if scale != 1:
            bone_points = image.info.get('bone_points', {})
            origin = image.info['origin']
            image = image.resize((max(1, round(image.width*scale)), max(1, round(image.height*scale))),
                                 Image.Resampling.LANCZOS)
            image.info['origin'] = tuple(v*scale for v in origin)
            image.info['bone_points'] = {key: tuple(v*scale for v in point) for key, point in bone_points.items()}
        return image

    @lru_cache(maxsize=128)
    def pet_clip_duration(self, species, animation):
        from spine_renderer import skeleton, animation_duration
        row = self.tables['Pet'][str(species)]
        path = self.spine_path(row['filePath'])
        if path is None:
            return 0
        return animation_duration(skeleton(str(path)).get('animations', {}).get(animation, {}))

    @lru_cache(maxsize=64)
    def armature_source(self, name):
        folder = self.assets/'Sprite/CcsAni'
        export = folder/f'{name}.ExportJson'
        if not export.exists():
            matches = list(self.assets.rglob(f'{name}.ExportJson'))
            if not matches:
                return None, None
            export = matches[0]
        folder = export.parent
        data = json.loads(export.read_text(encoding='utf-8'))
        return folder, data

    @lru_cache(maxsize=64)
    def armature_frames(self, name):
        folder, data = self.armature_source(name)
        if data is None:
            return {}
        frames = {}
        for plist in folder.glob(f'{name}[0-9]*.plist'):
            raw = plist.read_bytes()
            if raw.startswith(b'\xef\xbb\xbf'):
                # Cocos Studio exports some X plists with a UTF-8 BOM.
                raw = raw[3:]
            # Cocos Studio writes <ustring> for UTF-8 strings; plistlib only
            # accepts <string>, so normalize before parsing.
            raw = raw.replace(b'<ustring>', b'<string>').replace(b'</ustring>', b'</string>')
            pd = plistlib.loads(raw)
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
        return frames

    def armature(self, name, animation='standdown', frame=0, *, viewport=None):
        if name in ('niudanji', 'ndchongwubeijingguang') and getattr(self, 'enable_baked', True):
            from animation_cache import load_manifest, read_frame
            if not hasattr(self, '_lottery_cache_manifest'):
                self._lottery_cache_manifest = load_manifest(self)
            if self._lottery_cache_manifest:
                root, manifest = self._lottery_cache_manifest
                clip = manifest['clips'].get(name+'/'+animation)
                if clip and (not clip.get('viewport') or tuple(clip['viewport']) == viewport):
                    index = int(frame) % clip['duration'] if clip['loop'] else min(max(0, int(frame)), clip['duration']-1)
                    origin = clip['origins'][index]
                    if origin is None:
                        return None
                    try:
                        return read_frame(str(root), name, animation, index, tuple(origin))
                    except OSError:
                        pass
        return self._render_armature(name, animation, frame)

    @lru_cache(maxsize=1024)
    def _render_armature(self, name, animation='standdown', frame=0):
        """Software preview of Cocos Studio bones, including original texture pivots."""
        _, data = self.armature_source(name)
        frames = self.armature_frames(name)
        if not frames:
            return None
        moves = (data.get('animation_data') or [{}])[0].get('mov_data', []) or []
        move = next((m for m in moves if m['name'] == animation), moves[0] if moves else {})
        if move.get('lp') and move.get('dr', 0) > 0:
            frame %= move['dr']
        active = {}
        from ccs_timeline import sample_frame
        for bone in move.get('mov_bone_data', []) or []:
            fd = bone.get('frame_data', []) or []
            if fd:
                active[bone['name']] = sample_frame(fd, frame)
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
            if sprite is None or sprite.width <= 0 or sprite.height <= 0:
                # A few trimmed atlas entries export a zero-sized frame.
                # They cannot be scaled or composited; skip just that skin.
                continue
            color = f.get('color', {})
            if color.get('a', 255) <= 0:
                continue
            if any(color.get(key, 255) != 255 for key in ('r', 'g', 'b', 'a')):
                sprite = Image.merge('RGBA', tuple(channel.point(
                    lambda value, amount=color.get(key, 255): round(value*amount/255))
                    for channel, key in zip(sprite.split(), ('r', 'g', 'b', 'a'))))
            skin = disp.get('skin_data', [{}])[0]
            m = multiply(transform(name_), matrix(skin))
            tex = texture.get(disp['name'], {})
            # Some original exports (notably npc20) omit texture_data. Their
            # atlas is content-scaled but bones/skins remain in authored units.
            # Treating atlas pixels as bone units shrinks and separates limbs.
            texture_scale = float(data.get('content_scale', .5) or .5)
            tw = float(tex.get('width', sprite.width/texture_scale))
            th = float(tex.get('height', sprite.height/texture_scale))
            px, py = float(tex.get('pX', .5)), float(tex.get('pY', .5))
            m = multiply(m, (tw/sprite.width, 0, 0, -th/sprite.height, -tw*px, th*(1-py)))
            parts.append((bone.get('z', 0)+f.get('z', 0), sprite, m))
        if not parts:
            return None
        # Bound the transformed skins before rasterizing. Keeping the authored
        # origin separately prevents animation bounds from moving the feet.
        points = []
        for _, sprite, m in parts:
            a, b, c, d, tx, ty = m
            for x, y in ((0, 0), (sprite.width, 0), (0, sprite.height), (sprite.width, sprite.height)):
                points.append(((a*x+c*y+tx)*.5, -(b*x+d*y+ty)*.5))
        left = math.floor(min(p[0] for p in points))-2
        top = math.floor(min(p[1] for p in points))-2
        right = math.ceil(max(p[0] for p in points))+2
        bottom = math.ceil(max(p[1] for p in points))+2
        out = Image.new('RGBA', (max(1, right-left), max(1, bottom-top)))
        origin = (-left, -top)
        for _, sprite, m in sorted(parts, key=lambda p: p[0]):
            a, b, c, d, tx, ty = m
            a, c, tx = a*.5, c*.5, tx*.5+origin[0]
            b, d, ty = -b*.5, -d*.5, -ty*.5+origin[1]
            det = a*d-b*c
            if abs(det) < 1e-8:
                continue
            inv = (d/det, -c/det, (c*ty-d*tx)/det,
                   -b/det, a/det, (b*tx-a*ty)/det)
            # Warp only this skin's bounds, not the entire armature canvas for
            # every bone. The same affine matrix and painter order are retained.
            pad = math.ceil(2*max(abs(a)+abs(c), abs(b)+abs(d)))+1
            xs = [tx, a*sprite.width+tx, c*sprite.height+tx, a*sprite.width+c*sprite.height+tx]
            ys = [ty, b*sprite.width+ty, d*sprite.height+ty, b*sprite.width+d*sprite.height+ty]
            x0, y0 = max(0, math.floor(min(xs))-pad), max(0, math.floor(min(ys))-pad)
            x1, y1 = min(out.width, math.ceil(max(xs))+pad), min(out.height, math.ceil(max(ys))+pad)
            if x0 >= x1 or y0 >= y1:
                continue
            local = (inv[0], inv[1], inv[2]+inv[0]*x0+inv[1]*y0,
                     inv[3], inv[4], inv[5]+inv[3]*x0+inv[4]*y0)
            layer = sprite.transform((x1-x0, y1-y0), Image.Transform.AFFINE, local,
                                     resample=Image.Resampling.BICUBIC)
            out.alpha_composite(layer, (x0, y0))
        box = out.getbbox()
        if not box:
            return None
        result = out.crop(box)
        result.info['origin'] = (origin[0]-box[0], origin[1]-box[1])
        return result

    def load_map(self, map_id):
        info = self.tables['VillageMap'][str(map_id)]
        # Recovered X 2.10.9 stores the Light City landing as a decorative
        # tile object; the original client still lists it as an exit.
        if str(map_id) == '2101' and info.get('fileName') == 'map2101.tmx':
            info['exitIds'] = '210101,210102'
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
        references = self.xml.findall('tileset')
        missing_tilesets = []
        for index, reference in enumerate(references):
            source = reference.get('source')
            tileset_path = self.path.parent/source if source else self.path
            if source and not tileset_path.is_file():
                first = int(reference.get('firstgid'))
                stop = int(references[index+1].get('firstgid')) if index+1 < len(references) else 1 << 29
                missing_tilesets.append((first, stop, source))
                continue
            ts = ET.parse(tileset_path).getroot() if source else reference
            image = ts.find('image')
            if image is None:
                continue
            properties = {int(t.get('id')): props(t) for t in ts.findall('tile')}
            image_path = (tileset_path.parent/image.get('source')).resolve()
            assets = self.data.assets.resolve()
            asset_path = (image_path.relative_to(assets).as_posix()
                          if image_path.is_relative_to(assets) else 'Map/'+image_path.name)
            self.tilesets.append({'first': int(reference.get('firstgid')), 'name': ts.get('name'),
                                  'image': asset_path, 'props': properties,
                                  'tw': int(ts.get('tilewidth')), 'th': int(ts.get('tileheight'))})
        for node in self.xml.findall('layer'):
            content = node.find('data')
            encoding, compression = content.get('encoding'), content.get('compression')
            if encoding == 'base64':
                b = base64.b64decode(content.text)
                if compression == 'zlib':
                    b = zlib.decompress(b)
                elif compression == 'gzip':
                    b = gzip.decompress(b)
                vals = struct.unpack('<'+'I'*(len(b)//4), b)
            elif encoding == 'csv':
                vals = tuple(int(s.strip()) for s in content.text.split(',') if s.strip())
            else:
                vals = tuple(int(t.get('gid', 0)) for t in content.findall('tile'))
            self.layers.append((node.get('name'), vals, float(node.get('opacity', 1))))
        for group in self.xml.findall('objectgroup'):
            for node in group.findall('object'):
                self.objects.append({'group': group.get('name'), **node.attrib, 'props': props(node)})
        if self.path.name == 'map1101.tmx':
            # The underwater return portal is stored under spriteTileLayer in
            # the recovered X file, but the original client treats it as an
            # exit object; move it before exit/collision dispatch.
            for obj in self.objects:
                if obj.get('name') == '110108' and obj.get('props', {}).get('toExit') == '570102':
                    obj['group'] = 'spriteLayer'
        if self.path.name == 'map7502.tmx':
            # A decorative floor-2 switch stone occupies area 750201's only
            # trigger tile.  The original marks it walk-through.
            for obj in self.objects:
                if obj.get('x') == '188.0' and obj.get('y') == '1464.0' and obj.get('gid'):
                    obj.setdefault('props', {})['pcWalkThrough'] = '1'
        if missing_tilesets:
            used = {gid & 0x1fffffff for _, layer, _ in self.layers for gid in layer}
            used.update(int(obj.get('gid', 0)) & 0x1fffffff for obj in self.objects)
            for first, stop, source in missing_tilesets:
                if any(first <= gid < stop for gid in used):
                    raise FileNotFoundError(f'{self.path.name}: missing referenced tileset {source}')
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
                ty = int((float(obj['y'])-self.th/2)//self.th)
                self.obstacles[(tx, ty)] = obs
        self.removed_obstacles = set()
        self.sprite_collision = set()
        self.named_scenery_collision = {}
        self.hidden_scenery = set()
        self._scenery = None
        for obj in self.objects:
            if obj['group'] != 'spriteTileLayer' or not obj.get('gid'):
                continue
            if obj['props'].get('pcWalkThrough') == '1':
                continue
            properties = self.tile_properties(int(obj['gid']))
            if int(properties.get('obsType', 0)):
                continue  # Breakable objects use the removable obstacle layer.
            definition = data.sprite_tiles().get(str(properties.get('spriteId')), {})
            # createSpriteTile 0x2df41e..0x2df43a adds half a tile in
            # Cocos bottom-origin coordinates before registering collision.
            tx, ty = int(float(obj['x'])//self.tw), int((float(obj['y'])-self.th/2)//self.th)
            for dx, dy in json.loads(definition.get('collideInfo', '[]')):
                cell = (tx+int(dx), ty-int(dy))
                if 0 <= cell[0] < self.width and 0 <= cell[1] < self.height:
                    name = obj.get('name')
                    if name:
                        self.named_scenery_collision.setdefault(name, set()).add(cell)
                    else:
                        self.sprite_collision.add(cell)
        self._fixed_sprite_collision = self.sprite_collision.copy()
        self.set_hidden_scenery(set())

    def set_hidden_scenery(self, names):
        self.hidden_scenery = set(names)
        self.sprite_collision = self._fixed_sprite_collision.copy()
        for name, cells in self.named_scenery_collision.items():
            if name not in self.hidden_scenery:
                self.sprite_collision.update(cells)

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
        if not (self.data.assets/ts['image']).exists() and Path(ts['image']).name not in self.data.image_paths:
            return None
        image = self.data.image(ts['image'])
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
            for x, y, tile in sorted(self.scenery(), key=lambda item: item[1]):
                ax, ay = tile.info.get('origin', (tile.width/2, tile.height))
                out.alpha_composite(tile, (round(x-ax), round(y-ay)))
        return out.resize((round(size[0]*scale), round(size[1]*scale)), Image.Resampling.LANCZOS)

    def scenery(self):
        if self._scenery is None:
            self._scenery = []
            images = {}
            for obj in self.objects:
                if obj['group'] != 'spriteTileLayer' or not obj.get('gid'):
                    continue
                gid = int(obj['gid'])
                sid = self.tile_properties(gid).get('spriteId')
                animation = obj['props'].get('aniName') or 'standdown'
                key = (sid or gid, animation)
                if key not in images:
                    image = self.data.village_sprite(sid, animation) if sid else self.tile(gid)
                    if image is not None:
                        image = image.copy()
                        definition = self.data.sprite_tiles().get(str(sid))
                        if definition:
                            image.info['origin'] = (image.width/2-float(definition['x']),
                                                    image.height/2+float(definition['y']))
                    images[key] = image
                if images[key] is not None:
                    self._scenery.append((float(obj['x'])+self.tw/2, float(obj['y'])-self.th/2, images[key], obj.get('name')))
        return [(x, y, image) for x, y, image, name in self._scenery
                if name not in self.hidden_scenery
                and (int((x-self.tw/2)//self.tw), int(y//self.th)) not in self.removed_obstacles]

    def sprite_blocked(self, x, y, mounts=None):
        cell = (int(x//self.tw), int(y//self.th))
        if cell not in getattr(self, 'sprite_collision', set()):
            return False
        return not (mounts is not None and mounts.can_fly(int(self.info['mapType'])))

    def terrain_at(self, x, y):
        """Original collideTile category, or None outside the map."""
        tx, ty = int(x//self.tw), int(y//self.th)
        if not (0 <= tx < self.width and 0 <= ty < self.height):
            return None
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

    def blocked(self, x, y, mounts=None, *, allow_break=False):
        terrain = self.terrain_at(x, y)
        if terrain is None or self.sprite_blocked(x, y, mounts):
            return True
        # obsType and collideTile are separate native enums: rock=2 is NOT
        # water=2. Owning a swimming mount must never auto-board a rock.
        obstacle = self.obstacle_at(x, y)
        flying = mounts is not None and mounts.can_fly(int(self.info['mapType']))
        if obstacle and not flying:
            if not (allow_break and mounts is not None and mounts.obstacle_ability(obstacle)):
                return True
        if mounts is None:
            return terrain != 0
        return not mounts.can_enter(terrain, int(self.info['mapType']))

    def route_blocked(self, x, y, mounts=None):
        """Plan through breakable obstacles; actual movement removes them first."""
        return self.blocked(x, y, mounts, allow_break=True)
