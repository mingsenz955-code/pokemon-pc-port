import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from pc_game import NativeGame

data = OriginalData(ROOT/'original-1.20.4')
counts = Counter()
examples = {}
for path in (ROOT/'original-1.20.4/assets/PlotEvent').glob('pEvent*.json'):
    if path.name == 'pEventContents.json':
        continue
    try:
        steps = data.event(path.name)
    except Exception:
        continue
    for step in steps:
        if step.get('type') != 'openui':
            continue
        params = step.get('parameters', {})
        uiid = int(params.get('uiid', 0) or 0)
        counts[uiid] += 1
        examples.setdefault(uiid, []).append((path.name, params))
known = set(NativeGame.UI_LAYOUTS)
print('uiids=', len(counts), 'known=', sorted(known))
print('unknown=', [(u, counts[u], examples[u][:1]) for u in sorted(counts) if u not in known])