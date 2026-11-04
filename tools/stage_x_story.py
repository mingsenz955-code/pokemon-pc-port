"""Assemble the APK's story and maps for testing in a separate PC data directory."""
import argparse
import json
import shutil
from pathlib import Path

from audit_story_migration import audit, numbers


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
    for file in (source/'events').glob('*.json'):
        target = output/'events'/file.name
        rows = json.loads(file.read_bytes())
        if file.name != 'pEventContents.json':
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
        write_json(target, rows)
    write_json(output/'tables.json', pc)
    report['retained_pc_event_versions'] = sorted(retained_events)
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
