import json, collections
d = json.load(open('original-1.20.4/tables.json', encoding='utf-8'))
skills = d['Skill']
print('types', collections.Counter(s['type'] for s in skills.values()))
print('mainAttribute', collections.Counter(s['mainAttribute'] for s in skills.values()))
print('attackCount', collections.Counter(s['attackCount'] for s in skills.values()))
print('attackCoe', collections.Counter(s['attackCoe'] for s in skills.values()))
print('attackRate', collections.Counter(s['attackRate'] for s in skills.values()))
print('bodyPos', collections.Counter(s['bodyPos'] for s in skills.values()))
print('effectpos', collections.Counter(s['effectpos'] for s in skills.values()))
print('shake', collections.Counter(s['shake'] for s in skills.values()))
print('skillLevel', collections.Counter(s['skillLevel'] for s in skills.values()))
for k, s in sorted(skills.items(), key=lambda kv: int(kv[0])):
    print(f"{k}\t{s['name']}\ttype={s['type']} attr={s['mainAttribute']} atk={s['attack']} coe={s['attackCoe']} cnt={s['attackCount']} rate={s['attackRate']} cost={s['energyCost']} cd={s['coolDown']} state={s['state']} state2={s['state2']} crit={s['critRevise']}\t{s['des']}")