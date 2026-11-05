"""Compare atlas decoding with the repository baseline; sample current battles."""
import importlib.util
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from PIL import ImageChops

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools'))
import spine_renderer
from check_restoration_097 import DATA, OUT, host

baseline = ModuleType('baseline_spine')
source = subprocess.run(['git', 'show', 'HEAD:src/spine_renderer.py'], cwd=ROOT,
                        check=True, capture_output=True).stdout.decode('utf-8')
exec(compile(source, 'baseline_spine_renderer.py', 'exec'), baseline.__dict__)
paths = list(DATA.assets.rglob('*.atlas'))
path = max(paths, key=lambda p: p.stat().st_size)
report = {'context': 'CPU render benchmark; not display FPS; same APK assets and atlas for both versions',
          'atlas': str(path.relative_to(DATA.assets))}
images = {}
for name, module in [('before', baseline), ('after', spine_renderer)]:
    samples = []
    for _ in range(3):
        module.atlas_regions.cache_clear()
        start = time.perf_counter()
        regions = module.atlas_regions(path)
        samples.append((time.perf_counter()-start)*1000)
    images[name] = regions
    report['atlas_'+name] = {'median_ms': round(statistics.median(samples), 3), 'regions': len(regions)}
assert images['before'].keys() == images['after'].keys()
for key in images['before']:
    assert images['before'][key].size == images['after'][key].size
    assert ImageChops.difference(images['before'][key], images['after'][key]).getbbox() is None
report['atlas_pixels_identical'] = True
report['atlas_speedup'] = round(report['atlas_before']['median_ms']/report['atlas_after']['median_ms'], 2)
ui = host()
for name, skill in [('idle', None), ('wind', '300030'), ('tornado', '300033')]:
    samples = []
    if skill:
        plan = ui.effects.plan(skill, 'player')
        ui.anim = {'kind': 'skill', 'side': 'player', 'target': 'enemy', 'effect': plan,
                   'age': 0, 'duration': plan['duration'], 'amount': 0, 'damages': []}
    else:
        ui.anim = None
    for i in range(120):
        ui.anim_idle = i*25/60
        if ui.anim:
            ui.anim['age'] = i*25/60
        ui.frame = None
        start = time.perf_counter()
        ui.render()
        samples.append((time.perf_counter()-start)*1000)
    ordered = sorted(samples)
    report[name] = {'median_ms': round(statistics.median(samples), 3),
                    'p95_ms': round(ordered[int(.95*(len(ordered)-1))], 3),
                    'worst_ms': round(max(samples), 3)}
(OUT/'performance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
