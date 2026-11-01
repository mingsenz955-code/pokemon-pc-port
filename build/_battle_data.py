import json
d = json.load(open('original-1.20.4/tables.json', encoding='utf-8'))
print('NpcFight keys', list(d['NpcFight'])[:30])
print('Npc rows')
for k, v in d['Npc'].items():
    print(k, json.dumps(v, ensure_ascii=False))
print('NpcFight 511051 / 1002011')
for k in ['511051', '1002011', '1002012']:
    print(k, d['NpcFight'].get(k))
print('sample VillageEnemy 607001', d['VillageEnemy']['607001'])
print('Pet 100001')
print(json.dumps(d['Pet']['100001'], ensure_ascii=False, indent=1))
print('Skill 300001/300056/300100')
for k in ['300001', '300056', '300100']:
    print(k, json.dumps(d['Skill'].get(k), ensure_ascii=False))
print('SkillState all')
for k, v in d['SkillState'].items():
    print(k, json.dumps(v, ensure_ascii=False))