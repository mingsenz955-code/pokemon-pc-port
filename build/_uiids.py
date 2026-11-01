import json, os, collections
root = 'original-1.20.4/events'
rows = collections.defaultdict(list)
for name in os.listdir(root):
    if not name.endswith('.json') or name.startswith('pEventContents'):
        continue
    steps = json.load(open(os.path.join(root, name), encoding='utf-8'))
    if not isinstance(steps, list):
        continue
    for i, s in enumerate(steps):
        if s.get('type') == 'openui':
            before = steps[i-1].get('text', '') if i else ''
            rows[s['parameters']['uiid']].append((name, before, s.get('parameters', {})))
for key in sorted(rows):
    values = rows[key]
    print(key, len(values), values[0][0], '|', values[0][1][:70], '|', values[0][2])
    if len(values) > 1:
        print('    ', values[1][0], '|', values[1][1][:70], '|', values[1][2])