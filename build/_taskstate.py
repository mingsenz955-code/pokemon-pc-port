import json, os
root = 'original-1.20.4/events'
for name in os.listdir(root):
    if not name.endswith('.json') or name.startswith('pEventContents'):
        continue
    for s in json.load(open(os.path.join(root, name), encoding='utf-8')):
        if isinstance(s, dict) and s.get('type') == 'taskstate':
            p = s.get('parameters', {})
            if isinstance(p, dict) and p.get('mtask') in (2, 3):
                print(name, s)
            elif isinstance(p, list) and any(x.get('mtask') in (2, 3) for x in p):
                print(name, s)