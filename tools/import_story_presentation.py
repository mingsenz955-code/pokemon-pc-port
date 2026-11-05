"""Apply the reviewed presentation slice of the recovered X package to a PC build."""
import json
import shutil
import xml.etree.ElementTree as ET


def apply_pet_catalog(pc_data, recovered):
    path = pc_data/'tables.json'
    tables = json.loads(path.read_bytes())
    source = json.loads((recovered/'tables.json').read_bytes())
    for table in ('Pet', 'Skill', 'SkillEffect', 'SkillState', 'StateDescribe',
                  'Talent', 'Sound', 'PetAttributeEnum', 'PetLandType', 'PetKindEnum'):
        tables[table].update({key: row for key, row in source[table].items()
                              if key not in tables[table]})
    for table, cost in (('Evolution', 'itemIds'), ('PetHeTi', 'costItemIds')):
        known = tables['Item'].keys() | tables['Money'].keys() | {'0'}
        tables[table].update({key: row for key, row in source[table].items()
                              if key not in tables[table] and set(row[cost].split(',')) <= known})
    path.write_text(json.dumps(tables, ensure_ascii=False, indent=2), encoding='utf-8')
    for folder in ('Sprite', 'PetHead', 'Skill', 'Audio'):
        source_dir = recovered/'assets'/folder
        for file in source_dir.rglob('*'):
            target = pc_data/'assets'/folder/file.relative_to(source_dir)
            if file.is_file() and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, target)


def apply_compatible_dialogue(pc_data, recovered):
    kinds = {'talk', 'aside', 'airtalk'}
    for path in (pc_data/'events').glob('*.json'):
        incoming = recovered/'events'/path.name
        if path.name == 'pEventContents.json' or not incoming.exists():
            continue
        base, source = (json.loads(file.read_bytes()) for file in (path, incoming))
        if len(base) != len(source):
            continue
        changed = False
        for step, reference in zip(base, source):
            old, new = step.get('text'), reference.get('text')
            if not isinstance(old, str) or not isinstance(new, str) or old == new or step.get('type') not in kinds:
                continue
            # Keep the same speaker, placement and command. In particular,
            # a replaced pet NPC must not introduce a different pet name.
            if old.partition(':')[0] != new.partition(':')[0]:
                continue
            if ({k: v for k, v in step.items() if k not in ('id', 'text')} !=
                    {k: v for k, v in reference.items() if k not in ('id', 'text')}):
                continue
            step['text'] = new
            changed = True
        if changed:
            path.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding='utf-8')


def apply_story_presentation(pc_data, recovered):
    apply_pet_catalog(pc_data, recovered)
    apply_compatible_dialogue(pc_data, recovered)
    # Keep save-visible step IDs and instructions, including dialogue portraits.
    updates = {
        'pEventBTask13301.json': {14: ('急冻鸟:喔吼！！！', '闪电鸟:喔吼！！！')},
        'pEventTalk50715.json': {2: ('希德:我要成为这个世界上第一个创造飞行艇的人！',
                                    '希德:我是这个世界上第一个创造飞行艇的人！')},
    }
    for name, lines in updates.items():
        path = pc_data/'events'/name
        script = json.loads(path.read_bytes())
        source = json.loads((recovered/'events'/name).read_bytes())
        for step_id, (old, new) in lines.items():
            step = next(s for s in script if s['id'] == step_id)
            if step['type'] != 'talk' or step['text'] not in (old, new) or not any(
                    s['type'] == 'talk' and s.get('text') == new for s in source):
                raise ValueError(f'Unexpected dialogue in {name}, step {step_id}')
            step['text'] = new
        path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding='utf-8')

    # Nanny's house uses the new visual layers with the PC furniture,
    # collision and interaction groups. The X-only exit stays absent.
    current = pc_data/'assets/Map'
    incoming = recovered/'assets/Map'
    path = current/'map5807.tmx'
    base = ET.parse(path).getroot()
    updated = ET.parse(incoming/path.name).getroot()
    dimensions = ('width', 'height', 'tilewidth', 'tileheight')
    if any(base.get(key) != updated.get(key) for key in dimensions):
        raise ValueError('Nanny’s house changed grid dimensions')
    atlas_selector = "tileset[@name='map5']"
    if base.find(atlas_selector).get('firstgid') != updated.find(atlas_selector).get('firstgid'):
        raise ValueError('Nanny’s house changed tile identifiers')
    for node in list(base):
        if node.tag == 'layer' and node.get('name') != 'collideLayer':
            replacement = next(layer for layer in updated.findall('layer')
                               if layer.get('name') == node.get('name'))
            index = list(base).index(node)
            base.remove(node)
            base.insert(index, replacement)
    atlas = base.find(atlas_selector+'/image')
    atlas.set('source', 'x-map5807.png')
    shutil.copyfile(incoming/'map5.png', current/'x-map5807.png')
    ET.ElementTree(base).write(path, encoding='utf-8', xml_declaration=True)
