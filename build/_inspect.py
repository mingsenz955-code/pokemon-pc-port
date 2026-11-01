import json
d = json.load(open('original-1.20.4/tables.json', encoding='utf-8'))
for k in ['NpcFight','Skill','SkillEffect','SkillState','Talent','Cri','PetQuality','PetHeTi','PetTuPo','FightRank','VillageEnemy','BossPet','Boss','Arena','ArenaNpc','InitPet','Init','PetAttributeEnum','StateDescribe','Contrast','SkillItem','PetItem','Function']:
    v = d[k]
    key = next(iter(v))
    print('='*20, k, len(v))
    print(json.dumps(v[key], ensure_ascii=False, indent=1)[:1600])