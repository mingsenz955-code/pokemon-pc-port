"""Recovered areaMap TMX geometry and original nine-slice map tiles.

VillageAreaMapUiLayer::initAreaMapUi 0x3c6acc reads mapLayer/exitLayer.
VillageAreaMapSprite::initWithMapId 0x3c6074 uses areaMapBottom%d.png,
10-pixel cap insets and a 20-pixel map name, not a screenshot of the village.
"""
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw
from csb_render import nine_slice


def parent_map(data, mid):
    seen = set()
    key = str(mid)
    while key not in seen:
        seen.add(key)
        row = data.tables['VillageMap'].get(key, {})
        parent = str(row.get('parentMapId', key))
        if parent in ('0', key) or parent not in data.tables['VillageMap']:
            return key
        key = parent
    return key


def region_for(data, mid):
    mid = parent_map(data, mid)
    return next((key for key, row in data.tables['WorldMap'].items()
                 if mid in str(row['mapIds']).split(',')), '1')


def region_image(app, region):
    data = app.data
    row = data.tables['WorldMap'][str(region)]
    xml = ET.parse(data.assets/'Map'/row['fileName']).getroot()
    width = int(xml.get('width'))*int(xml.get('tilewidth'))
    height = int(xml.get('height'))*int(xml.get('tileheight'))
    frame = Image.new('RGBA', (width, height))
    visited = {parent_map(data, m) for m in app.state.visited_maps}
    current = parent_map(data, app.map_id)
    target = app.guide.resolver.target()
    destination = parent_map(data, target.map_id) if target and target.map_id else None
    boxes = {}
    draw = ImageDraw.Draw(frame)
    font = app.cocos_ui.font('', 20)
    for obj in xml.findall('./objectgroup[@name="mapLayer"]/object'):
        mid = obj.get('name')
        x, y, w, h = (round(float(obj.get(k, 0))) for k in ('x', 'y', 'width', 'height'))
        boxes[mid] = (x, y, x+w, y+h)
        tile = data.image('Map/areaMapBottom%d.png' % (2 if mid in visited else 1))
        frame.alpha_composite(nine_slice(tile, (w, h), (10, 10, tile.width-20, tile.height-20)), (x, y))
        name = data.tables['VillageMap'].get(mid, {}).get('name', mid)
        draw.text((x+w/2, y+h/2), name, font=font, anchor='mm', fill='#ffffff',
                  stroke_width=1, stroke_fill='#6b492a')
        if mid == destination:
            # Main task icon 12 (available) / 13 (in progress) / 14
            # (submit) uses the original task icon family at native scale .8.
            status = int(app.state.main_state)
            icon = data.image('TaskIcon/taskIcon%d.png' % {2: 12, 3: 13, 4: 14}.get(status, 13))
            icon = icon.resize((round(icon.width*.8), round(icon.height*.8)), Image.Resampling.LANCZOS)
            frame.alpha_composite(icon, (round(x+w/2-icon.width/2), round(y+h/2-icon.height/2)))
        if mid == current:
            icon = data.image('Map/areaMapPlayerHead.png')
            frame.alpha_composite(icon, (round(x+w/2-icon.width/2), y-24))
    for obj in xml.findall('./objectgroup[@name="exitLayer"]/object'):
        gid = int(obj.get('gid', 0)) & 0x1fffffff
        if not 1 <= gid <= 6:
            continue
        icon = data.image(f'Map/areaMapExit{gid}.png')
        frame.alpha_composite(icon, (round(float(obj.get('x'))), round(float(obj.get('y'))-icon.height)))
    return frame, boxes
