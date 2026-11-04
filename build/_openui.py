import json, os, collections
root = 'original-1.20.4/events'
by_ui = collections.defaultdict(list)
for name in sorted(os.listdir(root)):
    if not name.endswith('.json') or name.startswith('pEventContents'):
        continue
    steps = json.load(open(os.path.join(root, name), encoding='utf-8'))
    if not isinstance(steps, list):
        continue
    for i, s in enumerate(steps):
        if s.get('type') in ('openui', 'closeui'):
            by_ui[s['type']].append((name, i, s))
for kind in ['openui', 'closeui']:
    print('='*30, kind, len(by_ui[kind]))
    for name, i, s in by_ui[kind][:12]:
        steps = json.load(open(os.path.join(root, name), encoding='utf-8'))
        lo = max(0, i-2); hi = min(len(steps), i+3)
        print('---', name, 'index', i, json.dumps(s, ensure_ascii=False))
        for t in steps[lo:hi]:
            print('   ', t.get('id'), t.get('type'), (t.get('text') or '')[:50], json.dumps(t.get('parameters'), ensure_ascii=False)[:120])