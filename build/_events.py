import json, collections, os, re
root = 'original-1.20.4/events'
counts = collections.Counter()
samples = {}
keys = collections.defaultdict(collections.Counter)
for name in os.listdir(root):
    if not name.endswith('.json') or name.startswith('pEventContents'):
        continue
    try:
        steps = json.load(open(os.path.join(root, name), encoding='utf-8'))
    except Exception:
        continue
    if not isinstance(steps, list):
        continue
    for s in steps:
        t = s.get('type')
        counts[t] += 1
        if t not in samples:
            samples[t] = (name, s)
        p = s.get('parameters')
        if isinstance(p, dict):
            for k in p: keys[t][k] += 1
        elif isinstance(p, list):
            for row in p:
                if isinstance(row, dict):
                    for k in row: keys[t][k] += 1
print(counts.most_common())
print()
for t in ['fight','fightover','openui','closeui','wait','button','tapscreen','addteachnode','screen','screenflash','usefunction','function','goto','submittask','accepttask','costtaskitem','tempnpc','mainuivisible','iarenastate','init']:
    if t in samples:
        print('='*30, t, counts[t])
        print(json.dumps(samples[t], ensure_ascii=False, indent=1)[:1200])
        if keys[t]: print('keys:', dict(keys[t]))