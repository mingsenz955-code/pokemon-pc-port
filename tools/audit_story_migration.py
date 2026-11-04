"""Audit recovered story and map dependencies against the installed PC catalog."""
import argparse
import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'src'))
from game_state import numbers
from original_data import OriginalData


def audit(source, baseline):
    candidate = OriginalData(source)
    current = OriginalData(baseline)
    tables = candidate.tables
    new_pets = tables['Pet'].keys() - current.tables['Pet'].keys()
    required_pets = defaultdict(list)
    unmigrated_items = defaultdict(list)
    current_rewards = set().union(*(current.tables[table] for table in ('Pet', 'Item', 'Money')))

    def check_items(values, location):
        for item in numbers(values):
            if item and str(item) not in current_rewards and str(item) not in tables['Pet']:
                unmigrated_items[str(item)].append(location)

    for name in ('MainTask', 'BranchTask'):
        for key, task in tables[name].items():
            location = f'{name}/{key}'
            conditions = numbers(task.get('conditions', '0'))
            if int(task['conditionType']) == 3 and conditions and str(conditions[0]) in new_pets:
                required_pets[str(conditions[0])].append(location)
            for field in ('costIds', 'rewardIds'):
                check_items(task.get(field, '0'), f'{location}/{field}')

    for path in sorted((source/'events').glob('*.json')):
        if path.name == 'pEventContents.json':
            continue
        for index, step in enumerate(candidate.event(path.name), 1):
            parameters = step.get('parameters', {})
            rows = parameters if isinstance(parameters, list) else [parameters]
            for row in rows:
                if not isinstance(row, dict):
                    continue
                location = f'{path.stem}/{step.get("id", index)}'
                if step.get('type') == 'giveitem':
                    check_items(row.get('itemid', 0), location)
                if step.get('type') == 'fight':
                    fight = tables['NpcFight'].get(str(row.get('npcid')), {})
                    for key in numbers(fight.get('petIds', '0')):
                        pet = tables['NpcPet'].get(str(key), {}).get('petId')
                        if pet in new_pets:
                            required_pets[pet].append(location)

    map_errors = {}
    external_tilesets = []
    for key in tables['VillageMap']:
        try:
            world = candidate.load_map(key)
            if any(node.get('source') for node in world.xml.findall('tileset')):
                external_tilesets.append(key)
        except (OSError, ValueError, TypeError, KeyError, struct.error) as error:
            map_errors[key] = str(error)
    return {
        'configured_maps': len(tables['VillageMap']),
        'map_load_errors': map_errors,
        'maps_with_external_tilesets': external_tilesets,
        'new_story_pet_references': dict(required_pets),
        'item_references_needing_review': dict(unmigrated_items),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('recovery', type=Path)
    parser.add_argument('--baseline', type=Path, default=Path('original-1.20.4'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.recovery, args.baseline)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print({key: len(value) if isinstance(value, (dict, list)) else value for key, value in result.items()})
