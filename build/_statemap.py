import json, collections
d = json.load(open('original-1.20.4/tables.json', encoding='utf-8'))
use = collections.defaultdict(list)
for sid, s in d['Skill'].items():
    for field in ('state', 'state2'):
        raw = s.get(field, '') or ''
        nums = [x for x in raw.split(',') if x.strip()]
        for i in range(0, len(nums)-1, 2):
            if int(nums[i]) != 0:
                use[nums[i]].append((sid, s['name'], field, raw, s['des']))
for key in sorted(use, key=int):
    row = d['SkillState'].get(str(key), {})
    print('='*20, 'state', key, json.dumps(row, ensure_ascii=False))
    seen = set()
    for sid, name, field, raw, des in use[key]:
        if (sid, field) in seen: continue
        seen.add((sid, field))
        print(f'  {sid} {name} [{field}={raw}] {des}')