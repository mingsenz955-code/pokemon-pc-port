"""Software rendering of recovered Cocos layout images and text; no screenshot backgrounds."""
import json
import math
import os
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


def nine_slice(image, size, cap):
    width, height = max(1, round(size[0])), max(1, round(size[1]))
    x, y, w, h = [round(v) for v in cap]
    if w <= 0 or h <= 0 or x < 0 or y < 0 or x+w > image.width or y+h > image.height:
        return image.resize((width, height), Image.Resampling.LANCZOS)
    left, top, right, bottom = x, y, image.width-x-w, image.height-y-h
    if left+right > width:
        ratio = width/max(1, left+right)
        left, right = round(left*ratio), width-round(left*ratio)
    if top+bottom > height:
        ratio = height/max(1, top+bottom)
        top, bottom = round(top*ratio), height-round(top*ratio)
    src_x, src_y = [0, x, x+w, image.width], [0, y, y+h, image.height]
    dst_x, dst_y = [0, left, width-right, width], [0, top, height-bottom, height]
    result = Image.new('RGBA', (width, height))
    for row in range(3):
        for col in range(3):
            sw, sh = src_x[col+1]-src_x[col], src_y[row+1]-src_y[row]
            dw, dh = dst_x[col+1]-dst_x[col], dst_y[row+1]-dst_y[row]
            if min(sw, sh, dw, dh) <= 0:
                continue
            tile = image.crop((src_x[col], src_y[row], src_x[col+1], src_y[row+1]))
            tile = tile.resize((dw, dh), Image.Resampling.LANCZOS)
            result.alpha_composite(tile, (dst_x[col], dst_y[row]))
    return result


class CocosUI:
    def __init__(self, data):
        self.data = data
        self.hits = {}
        self.diagnostics = []

    @lru_cache(maxsize=64)
    def layout(self, name):
        source = self.data.assets/'res/UI'/(name+'.csb')
        if source.exists():
            from csb_reader import read_csb
            return read_csb(source)
        return json.loads((self.data.root/'ui-layouts'/name).with_suffix('.json').read_text(encoding='utf-8'))

    @lru_cache(maxsize=32)
    def font(self, filename, size):
        p = self.data.assets/'res'/filename
        if not filename or not p.exists():
            p = None
        if p is None or not p.exists():
            p = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts/msyh.ttc'
        return ImageFont.truetype(str(p), max(1, int(size)))

    def bitmap_text(self, resource, text):
        p = self.data.assets/'res'/resource
        if not p.exists():
            matches = list(self.data.assets.rglob(Path(resource).name))
            if not matches:
                return None
            p = matches[0]
        pages, glyphs, lineheight = {}, {}, 36
        for line in p.read_text(encoding='utf-8-sig').splitlines():
            values = {k: v.strip('"') for k, v in re.findall(r'(\w+)=((?:"[^"]*")|[^\s]+)', line)}
            if line.startswith('common '):
                lineheight = int(values.get('lineHeight', 36))
            elif line.startswith('page '):
                with Image.open(p.parent/values['file']) as im:
                    pages[int(values['id'])] = im.convert('RGBA')
            elif line.startswith('char '):
                glyphs[int(values['id'])] = {k: int(v) for k, v in values.items()}
        width = sum(glyphs.get(ord(c), {}).get('xadvance', 0) for c in text)
        result = Image.new('RGBA', (max(1, width), max(1, lineheight)))
        x = 0
        for c in text:
            g = glyphs.get(ord(c))
            if not g:
                continue
            tile = pages[g.get('page', 0)].crop((g['x'], g['y'], g['x']+g['width'], g['y']+g['height']))
            result.alpha_composite(tile, (x+g['xoffset'], g['yoffset']))
            x += g['xadvance']
        return result

    def render(self, name, size=(800, 480), text=None, visible=None, resources=None,
               offset=(0, 0), pressed=None, positions=None, rich_text=(), alphas=None,
               native_resources=(), percentages=None, sizes=None, canvas_size=None,
               auto_text=(), timeline_frame=None):
        layout = self.layout(name)
        root = layout['tree']
        design = canvas_size or root.get('size', [800, 480])
        if min(design) <= 0:
            design = [800, 480]
        frame = Image.new('RGBA', (round(design[0]), round(design[1])))
        self.hits, self.buttons, self.button_text, self.rects, self.diagnostics = {}, {}, {}, {}, []
        self.particles = []
        text, visible, resources = text or {}, visible or {}, resources or {}
        pressed = pressed or {}
        positions = positions or {}
        alphas = alphas or {}
        percentages = percentages or {}
        sizes = sizes or {}
        animated = {}
        if timeline_frame is not None:
            for track in layout.get('action', {}).get('tracks', []):
                frames = track['frames']
                if timeline_frame < frames[0]['frame']:
                    continue
                prior = frames[0]
                value = prior['value']
                for following in frames[1:]:
                    if timeline_frame < following['frame']:
                        if prior['tween'] and isinstance(value, list):
                            amount = (timeline_frame-prior['frame'])/max(1, following['frame']-prior['frame'])
                            value = [a+(b-a)*amount for a, b in zip(prior['value'], following['value'])]
                        break
                    prior, value = following, following['value']
                animated.setdefault(track['tag'], {})[track['property']] = value

        def visit(node, parent=(0, 0), scale=(1, 1), alpha=1, depth=0, prefix=''):
            if depth > 50:
                raise ValueError('Cocos UI project-node recursion limit')
            key = node.get('name', '')
            qualified = f'{prefix}/{key}' if prefix else key

            def resolve(mapping, default):
                if qualified in mapping:
                    return mapping[qualified]
                if key in mapping:
                    return mapping[key]
                for candidate, value in mapping.items():
                    if qualified.endswith('/'+candidate):
                        return value
                return default

            animation = animated.get(node.get('action_tag'), {})
            if not resolve(visible, animation.get('VisibleForFrame', node.get('visible', True))):
                return
            local = resolve(positions, animation.get('Position', node.get('position', [0, 0])))
            node_scale = animation.get('Scale', node.get('scale', [1, 1]))
            sx, sy = scale[0]*node_scale[0], scale[1]*node_scale[1]
            width, height = resolve(sizes, node.get('size', [0, 0]))
            if (key in auto_text or qualified in auto_text) and node['class'] == 'Text':
                value = str(resolve(text, node.get('text', '')))
                ft = self.font(node.get('font_resource', {}).get('path', ''), node.get('font_size', 22))
                width, height = max(1, math.ceil(ft.getlength(value))+2), ft.size+4
            anchor = node.get('anchor', [0, 0])
            x, y = parent[0]+local[0]*scale[0], parent[1]+local[1]*scale[1]
            origin = x-width*anchor[0]*sx, y-height*anchor[1]*sy
            alpha *= resolve(alphas, animation.get('Alpha', node.get('alpha', 255)))/255
            image = None
            if node['class'] == 'Particle' and node.get('resource', {}).get('path'):
                self.particles.append((node['resource']['path'], (x, frame.height-y), (sx, sy), alpha))
            resource = resolve(resources, node.get('resource', {}).get('path', ''))
            classname = node['class']
            # Original Cocos Button nodes carry a separate pressed texture.
            # Hover/press feedback therefore uses the game's own artwork rather
            # than a host-drawn rectangle.
            if classname == 'Button' and resolve(pressed, False):
                pressed_path = node.get('pressed', {}).get('path', '')
                if pressed_path:
                    resource = pressed_path
            if resource and classname not in ['TextBMFont', 'Particle']:
                try:
                    image = self.data.image('res/'+resource).copy()
                except (KeyError, OSError) as error:
                    self.diagnostics.append([key, resource, str(error)])
            if image:
                if key in native_resources or qualified in native_resources:
                    # ImageView::loadTexture + ignoreContentAdaptWithSize(true)
                    # uses the loaded icon's size, not the editor heart sample.
                    width, height = image.size
                width, height = resolve(sizes, (width, height))
                origin = x-width*anchor[0]*sx, y-height*anchor[1]*sy
                if width <= 0 or height <= 0:
                    width, height = image.size
                target = max(1, round(width*abs(sx))), max(1, round(height*abs(sy)))
                if node.get('scale9'):
                    # Cap insets remain at the texture's native resolution before
                    # the node's own scene scaling is applied.
                    image = nine_slice(image, (width, height), node.get('cap_insets', [0, 0, 0, 0]))
                image = image.resize(target, Image.Resampling.LANCZOS)
                if node.get('flip_x') or sx < 0:
                    image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if node.get('flip_y') or sy < 0:
                    image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                if alpha < 1:
                    image.putalpha(image.getchannel('A').point(lambda v: round(v*alpha)))
                if classname == 'LoadingBar' and (key in percentages or qualified in percentages):
                    fill = max(0, min(1, float(resolve(percentages, 1))))
                    image = image.copy()
                    image.paste((0, 0, 0, 0), (round(image.width*fill), 0, image.width, image.height))
                frame.alpha_composite(image, (round(origin[0]), round(frame.height-origin[1]-height*abs(sy))))
            elif (classname in ['Panel', 'ListView', 'ScrollView'] and node.get('background_type') == 1
                  and node.get('background_alpha', 255) > 0):
                a, r, g, b = node.get('background_color', [255, 255, 255, 255])
                background = Image.new('RGBA', frame.size)
                ImageDraw.Draw(background).rectangle((round(origin[0]), round(frame.height-origin[1]-height*sy),
                                                round(origin[0]+width*sx), round(frame.height-origin[1])),
                                               fill=(r, g, b, round(alpha*a*node.get('background_alpha', 255)/255)))
                frame.alpha_composite(background)
            value = str(resolve(text, node.get('text', '')))
            if value and classname in ['Text', 'Button', 'TextBMFont']:
                if classname == 'TextBMFont':
                    try:
                        glyphs = self.bitmap_text(node.get('resource', {}).get('path', ''), value)
                    except (KeyError, OSError, ValueError):
                        glyphs = None
                else:
                    glyphs = None
                if glyphs is not None:
                    # TextBMFont::setString updates content size. Anchors must
                    # follow the real glyph run, not the editor sample digits.
                    width, height = glyphs.size
                    origin = x-width*anchor[0]*sx, y-height*anchor[1]*sy
                if glyphs is None:
                    font = self.font(node.get('font_resource', {}).get('path', ''), node.get('font_size', 22))
                    value = re.sub(r'#[0-9]', '', value)
                    area = max(1, round(width)), max(1, round(height))
                    glyphs = Image.new('RGBA', area)
                    draw = ImageDraw.Draw(glyphs)
                    lines, current = [], ''
                    for char in value:
                        if char == '\n' or draw.textlength(current+char, font=font) > area[0]:
                            lines.append(current)
                            current = '' if char == '\n' else char
                        else:
                            current += char
                    lines.append(current)
                    if key in rich_text:
                        # RichTextEx replaces fixed-height editor Text nodes;
                        # its content height follows the wrapped text.
                        height = max(1, len(lines)*(font.size+3)-3)
                        origin = x-width*anchor[0]*sx, y-height*anchor[1]*sy
                        area = area[0], height
                        glyphs = Image.new('RGBA', area)
                        draw = ImageDraw.Draw(glyphs)
                    a, r, g, b = node.get('color', [255, 94, 61, 32])
                    line_height = font.size+3
                    ink_height = (len(lines)-1)*line_height+font.size
                    valign = node.get('vertical_alignment', 0)
                    y = max(0, (area[1]-ink_height)/2 if valign == 1 else area[1]-ink_height if valign == 2 else 0)
                    for index, line in enumerate(lines):
                        align = node.get('horizontal_alignment', 0)
                        remaining = area[0]-draw.textlength(line, font=font)
                        x = max(0, remaining/2 if align == 1 else remaining if align == 2 else 0)
                        draw.text((x, y+index*line_height), line, font=font, fill=(r, g, b, a), anchor='lt')
                if sx != 1 or sy != 1:
                    glyphs = glyphs.resize((max(1, round(glyphs.width*abs(sx))),
                                            max(1, round(glyphs.height*abs(sy)))), Image.Resampling.LANCZOS)
                frame.alpha_composite(glyphs, (round(origin[0]), round(frame.height-origin[1]-height*sy)))
            if node.get('touch') or classname == 'Button':
                rect = [origin[0], frame.height-origin[1]-height*sy,
                        origin[0]+width*sx, frame.height-origin[1]]
                self.hits[qualified] = rect
                self.hits[key] = rect
                if classname == 'Button':
                    self.buttons[qualified] = rect
                    self.button_text[qualified] = value
                    self.buttons[key] = rect
                    self.button_text[key] = value
            self.rects[qualified] = [origin[0], frame.height-origin[1]-height*sy,
                                     origin[0]+width*sx, frame.height-origin[1]]
            self.rects[key] = self.rects[qualified]
            for child in sorted(node.get('children', []), key=lambda c: c.get('z', 0)):
                visit(child, origin, (sx, sy), alpha, depth+1, qualified)
            if classname == 'ProjectNode' and node.get('project'):
                project = Path(node['project']).stem
                try:
                    visit(self.layout(project)['tree'], origin, (sx, sy), alpha, depth+1,
                          qualified)
                except FileNotFoundError:
                    self.diagnostics.append([key, project, 'Missing project layout'])
        visit(root, (offset[0]*design[0]/size[0], offset[1]*design[1]/size[1]))
        scale_x, scale_y = size[0]/design[0], size[1]/design[1]
        if (scale_x, scale_y) != (1, 1):
            self.particles = [(p, (x*scale_x, y*scale_y), (sx*scale_x, sy*scale_y), a)
                              for p, (x, y), (sx, sy), a in self.particles]
            for target in (self.hits, self.buttons, self.rects):
                for key, rect in list(target.items()):
                    target[key] = [rect[0]*scale_x, rect[1]*scale_y,
                                   rect[2]*scale_x, rect[3]*scale_y]
        return frame.resize(size, Image.Resampling.LANCZOS)
