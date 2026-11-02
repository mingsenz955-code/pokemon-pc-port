"""Read original Cocos Studio FlatBuffer layouts using the official CSParseBinary schema.

This reads layout data, not screenshots. Widget behavior remains a separate host
responsibility. The version and source file are retained in exported records.
"""
import struct
from pathlib import Path


class FlatTable:
    def __init__(self, buffer, position):
        self.b, self.p = buffer, position
        if position < 0 or position+4 > len(buffer):
            raise ValueError('FlatBuffer table outside file')
        self.v = position-self.unpack('<i', position)
        self.length = self.unpack('<H', self.v)
        if self.length < 4 or self.v+self.length > len(buffer):
            raise ValueError('Invalid FlatBuffer vtable')

    def unpack(self, fmt, position):
        return struct.unpack_from(fmt, self.b, position)[0]

    def field(self, slot):
        offset = self.unpack('<H', self.v+4+slot*2) if 4+slot*2 < self.length else 0
        return self.p+offset if offset else None

    def scalar(self, slot, fmt='<i', default=0):
        position = self.field(slot)
        return self.unpack(fmt, position) if position else default

    def pointer(self, slot):
        position = self.field(slot)
        return position+self.unpack('<I', position) if position else None

    def table(self, slot):
        position = self.pointer(slot)
        return FlatTable(self.b, position) if position else None

    def text(self, slot):
        position = self.pointer(slot)
        if not position:
            return ''
        size = self.unpack('<I', position)
        if position+4+size > len(self.b):
            raise ValueError('FlatBuffer string outside file')
        return self.b[position+4:position+4+size].decode('utf-8')

    def struct(self, slot, fmt, default):
        position = self.field(slot)
        return list(struct.unpack_from(fmt, self.b, position)) if position else default

    def tables(self, slot):
        position = self.pointer(slot)
        if not position:
            return []
        count = self.unpack('<I', position)
        result = []
        for index in range(count):
            base = position+4+index*4
            result.append(FlatTable(self.b, base+self.unpack('<I', base)))
        return result


def resource(table):
    if table is None:
        return {}
    return {'path': table.text(0), 'plist': table.text(1), 'type': table.scalar(2)}


def widget(table):
    if table is None:
        return {}
    return {'name': table.text(0), 'action_tag': table.scalar(1),
            'rotation': table.struct(2, '<ff', [0, 0]), 'z': table.scalar(3),
            'visible': bool(table.scalar(4, '<?', True)), 'alpha': table.scalar(5, '<B', 255),
            'tag': table.scalar(6), 'position': table.struct(7, '<ff', [0, 0]),
            'scale': table.struct(8, '<ff', [1, 1]), 'anchor': table.struct(9, '<ff', [0, 0]),
            'color': table.struct(10, '<BBBB', [255, 255, 255, 255]),
            'size': table.struct(11, '<ff', [0, 0]),
            'flip_x': bool(table.scalar(12, '<?')), 'flip_y': bool(table.scalar(13, '<?')),
            'ignore_size': bool(table.scalar(14, '<?')), 'touch': bool(table.scalar(15, '<?')),
            'callback_type': table.text(18), 'callback_name': table.text(19)}


def node(tree):
    classname = tree.text(0)
    wrapper = tree.table(2)
    options = wrapper.table(0) if wrapper else None
    result = {'class': classname, 'custom_class': tree.text(3)}
    if options:
        if classname in ['Node', 'SingleNode']:
            try:
                base_widget = widget(options)
            except (ValueError, UnicodeError, struct.error):
                base_widget = widget(options.table(0))
        else:
            try:
                base_widget = widget(options.table(0))
            except (ValueError, UnicodeError, struct.error) as error:
                raise ValueError(f'{classname} options at {options.p}: {error}') from error
        result.update(base_widget)
        if classname in ['Sprite', 'ImageView', 'Particle', 'GameMap', 'LoadingBar', 'TextBMFont']:
            result['resource'] = resource(options.table(1))
        if classname == 'ImageView':
            result['cap_insets'] = options.struct(2, '<ffff', [0, 0, 0, 0])
            result['scale9_size'] = options.struct(3, '<ff', [0, 0])
            result['scale9'] = bool(options.scalar(4, '<?'))
        elif classname == 'Button':
            result['resource'] = resource(options.table(1))
            result['pressed'] = resource(options.table(2))
            result['disabled'] = resource(options.table(3))
            result['font_resource'] = resource(options.table(4))
            result['text'] = options.text(5)
            # Localized text was added in newer schema versions. Retain raw field
            # offsets below so older version differences can be inspected.
            result['font_name'] = options.text(6)
            result['font_size'] = options.scalar(7)
            result['cap_insets'] = options.struct(9, '<ffff', [0, 0, 0, 0])
            result['scale9_size'] = options.struct(10, '<ff', [0, 0])
            result['scale9'] = bool(options.scalar(11, '<?'))
        elif classname == 'Text':
            result['font_resource'] = resource(options.table(1))
            result['font_name'] = options.text(2)
            result['font_size'] = options.scalar(3)
            result['text'] = options.text(4)
            result['text_area'] = [options.scalar(5), options.scalar(6)]
            result['horizontal_alignment'] = options.scalar(7)
            result['vertical_alignment'] = options.scalar(8)
            result['custom_text_size'] = bool(options.scalar(10, '<?'))
        elif classname == 'TextBMFont':
            result['text'] = options.text(2)
        elif classname in ['Panel', 'ScrollView', 'PageView', 'ListView']:
            result['resource'] = resource(options.table(1))
            result['clip'] = bool(options.scalar(2, '<?'))
            result['background_color'] = options.struct(3, '<BBBB', [255, 255, 255, 255])
            result['background_type'] = options.scalar(6)
            result['background_alpha'] = options.scalar(7, '<B', 255)
            result['cap_insets'] = options.struct(9, '<ffff', [0, 0, 0, 0])
            result['scale9_size'] = options.struct(10, '<ff', [0, 0])
            result['scale9'] = bool(options.scalar(11, '<?'))
        elif classname == 'ProjectNode':
            result['project'] = options.text(1)
    result['children'] = [node(child) for child in tree.tables(1)]
    return result


def read_csb(path):
    path = Path(path)
    buffer = path.read_bytes()
    root = FlatTable(buffer, struct.unpack_from('<I', buffer, 0)[0])
    tree = root.table(3)
    if tree is None:
        raise ValueError(f'No Cocos node tree in {path.name}')
    return {'source': path.name, 'version': root.text(0), 'tree': node(tree)}
