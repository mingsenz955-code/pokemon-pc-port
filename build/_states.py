import json
d = json.load(open('original-1.20.4/tables.json', encoding='utf-8'))
print('StateDescribe:')
for k, v in d['StateDescribe'].items():
    print(k, json.dumps(v, ensure_ascii=False))
print('\nTalent:')
for k, v in d['Talent'].items():
    print(k, json.dumps(v, ensure_ascii=False))
print('\nSkillEffect:')
for k, v in d['SkillEffect'].items():
    print(k, json.dumps(v, ensure_ascii=False))