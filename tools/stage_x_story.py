"""Assemble the APK's story and maps for testing in a separate PC data directory."""
import argparse
import json
import shutil
from pathlib import Path

from audit_story_migration import audit, numbers
from import_story_presentation import apply_pet_catalog, apply_compatible_dialogue


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def stage(source, baseline, output):
    report = audit(source, baseline)
    pc, apk = (json.loads((root/'tables.json').read_bytes()) for root in (baseline, source))
    # Explicit story and presentation tables. Keep the PC economy, items,
    # activities, initialization gifts and existing species definitions.
    for table in ('VillageMap', 'VillageExit', 'MainTask', 'BranchTask'):
        pc[table].update(apk[table])
    for table in ('WorldMap', 'VillageSprite', 'Npc', 'Sound', 'Skill', 'SkillEffect',
                  'SkillState', 'StateDescribe', 'Talent'):
        pc[table].update({key: row for key, row in apk[table].items() if key not in pc[table]})
    pc['Pet'].update({key: row for key, row in apk['Pet'].items() if key not in pc['Pet']})
    for table in ('NpcFight', 'NpcPet', 'BossPet', 'VillageEnemy'):
        for key, row in apk[table].items():
            if key not in pc[table] and ('petId' not in row or row['petId'] in pc['Pet']):
                pc[table][key] = row
    known = set(pc['Item']) | set(pc['Money']) | set(pc['Pet']) | {'0'}
    pc['StoryToken'] = {
        str(key): apk['Item'][str(key)]['name']
        for table in ('MainTask', 'BranchTask')
        for task in pc[table].values()
        for key in numbers(task['costIds'])
        if str(key) not in known
    }
    # The crystal petal is awarded and removed within the same quest scene.
    if '270101' in pc['StoryToken']:
        pc['StoryToken']['270100'] = apk['Item']['270100']['name']
    pc['StoryContinuation'] = {'155': 156}
    known |= pc['StoryToken'].keys()
    omitted_rewards = set()

    def retain_rewards(row, fields):
        vectors = [numbers(row[field]) for field in fields]
        if all(str(key) in known for key in vectors[0]):
            return
        entries = []
        for entry in zip(*vectors):
            if str(entry[0]) in known:
                entries.append(entry)
            else:
                omitted_rewards.add(str(entry[0]))
        for index, field in enumerate(fields):
            row[field] = ','.join(str(entry[index]) for entry in entries) or '0'

    for table in ('MainTask', 'BranchTask'):
        for task in pc[table].values():
            retain_rewards(task, ('rewardIds', 'rewardCounts'))
    for table in ('NpcFight', 'VillageEnemy'):
        for row in pc[table].values():
            retain_rewards(row, ('dropItemIds', 'dropItemCounts', 'dropPros'))
    for row in pc['VillageMap'].values():
        enemy_ids = numbers(row['enemyIds'])
        if not enemy_ids or enemy_ids == [0]:
            continue
        odds = numbers(row['enemyProbability'])
        if len(odds) == 1:
            odds *= len(enemy_ids)
        allowed = [(str(key), str(chance)) for key, chance in zip(enemy_ids, odds)
                   if str(key) in pc['VillageEnemy']]
        row['enemyIds'] = ','.join(key for key, _ in allowed) or '0'
        row['enemyProbability'] = ','.join(chance for _, chance in allowed) or '0'

    shutil.copytree(baseline, output)
    for folder in ('Map', 'Sprite', 'PetHead', 'Skill', 'Audio', 'FaceIcon'):
        src, dst = source/'assets'/folder, output/'assets'/folder
        for file in src.rglob('*'):
            if not file.is_file():
                continue
            target = dst/file.relative_to(src)
            if folder == 'Map' or not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, target)
    retained_events = []
    missing_scripts = []
    for file in (source/'events').glob('*.json'):
        target = output/'events'/file.name
        rows = json.loads(file.read_bytes())
        if file.name == 'pEventContents.json':
            missing_scripts = [row['id'] for row in rows
                               if not (source/'events'/f'pEvent{row["id"]}.json').is_file()
                               and not (baseline/'events'/f'pEvent{row["id"]}.json').is_file()]
            rows = [row for row in rows if row['id'] not in missing_scripts]
        else:
            if target.exists():
                if json.loads(target.read_bytes()) != rows:
                    retained_events.append(file.name)
                continue
            # X has standalone talk files with no numeric IDs. Assign free
            # IDs without shifting explicit goto targets or imported steps.
            used = {row['id'] for row in rows if 'id' in row}
            free = max(used, default=0)+1
            for row in rows:
                if 'id' not in row:
                    row['id'] = free
                    free += 1
                if row['type'] == 'giveitem':
                    rewards = row['parameters']
                    rewards = rewards if isinstance(rewards, list) else [rewards]
                    accepted = [reward for reward in rewards if str(reward['itemid']) in known]
                    omitted_rewards.update(str(reward['itemid']) for reward in rewards if reward not in accepted)
                    if accepted:
                        row['parameters'] = accepted
                    else:
                        row.update(type='eventstate', parameters=[])
        write_json(target, rows)
    write_json(output/'tables.json', pc)
    apply_pet_catalog(output, source)
    apply_compatible_dialogue(output, source)
    report['retained_pc_event_versions'] = sorted(retained_events)
    report['missing_trigger_scripts'] = missing_scripts
    report['omitted_reward_item_ids'] = sorted(omitted_rewards)
    report['story_token_ids'] = sorted(pc['StoryToken'])
    report['staged_species_count'] = len(pc['Pet'])
    report['unresolved_npc_fights'] = sorted(key for key, row in pc['NpcFight'].items()
                                            if any(str(pet) not in pc['NpcPet'] and str(pet) not in pc['BossPet']
                                                   for pet in numbers(row['petIds'])))
    write_json(output/'migration-audit.json', report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('recovery', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--baseline', type=Path, default=Path('original-1.20.4'))
    args = parser.parse_args()
    stage(args.recovery, args.baseline, args.output)
