import json, os
root = 'original-1.20.4/events'
for name in sorted(os.listdir(root)):
    if not name.endswith('.json') or name.startswith('pEventContents'):
        continue
    steps = json.load(open(os.path.join(root, name), encoding='utf-8'))
    if not isinstance(steps, list):
        continue
    for i, s in enumerate(steps):
        if s.get('type') == 'wait':
            lo = max(0, i-2); hi = min(len(steps), i+3)
            print('---', name, i, json.dumps(s, ensure_ascii=False))
            for t in steps[lo:hi]:
                print('   ', t.get('id'), t.get('type'), (t.get('text') or '')[:60], json.dumps(t.get('parameters'), ensure_ascii=False)[:100])