"""Pre-render original 60 Hz lottery poses losslessly; no altered source assets."""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from animation_cache import NAMES, REVISION, fingerprint

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=ROOT/'generated-assets/lottery')
args = parser.parse_args()
data = OriginalData(ROOT/'original-1.20.4')
data.enable_baked = False
sources = {name: fingerprint(data.armature_source(name)[0], name) for name in NAMES}
args.output.mkdir(parents=True, exist_ok=True)
path = args.output/'manifest.json'
if path.exists():
    old = json.loads(path.read_text(encoding='utf-8'))
    complete = all((args.output/name/clip/(str(i)+'.png')).is_file()
                   for key, row in old.get('clips', {}).items()
                   for name, clip in [key.split('/', 1)]
                   for i, origin in enumerate(row['origins']) if origin is not None)
    if old.get('revision') == REVISION and old.get('sources') == sources and old.get('clips') and complete:
        print('Original lottery cache is current.')
        raise SystemExit(0)
manifest = {'revision': REVISION, 'sources': sources, 'clips': {}}
for name in NAMES:
    _, source = data.armature_source(name)
    for move in source['animation_data'][0]['mov_data']:
        clip = move['name']
        duration = int(move['dr'])
        target = args.output/name/clip
        target.mkdir(parents=True, exist_ok=True)
        origins = []
        for frame in range(duration):
            image = data.armature(name, clip, frame)
            if image is not None and name == 'niudanji':
                # The native machine is anchored at (0,480) in an 800x480 UI.
                # Do not decode off-screen flying balls/glows on every frame.
                ox, oy = image.info['origin']
                box = (max(0, ox), max(0, oy-480), min(image.width, ox+800), min(image.height, oy))
                if box[0] >= box[2] or box[1] >= box[3]:
                    image = None
                else:
                    image = image.crop(box)
                    image.info['origin'] = (ox-box[0], oy-box[1])
            origins.append(list(image.info['origin']) if image is not None else None)
            if image is not None:
                image.save(target/(str(frame)+'.png'), compress_level=1)
            data._render_armature.cache_clear()
            if frame % 100 == 0:
                print(name, clip, f'{frame}/{duration}', flush=True)
        manifest['clips'][name+'/'+clip] = {'duration': duration, 'loop': bool(move.get('lp')), 'origins': origins,
                                         'viewport': [800, 480] if name == 'niudanji' else None}
        print(name, clip, 'done', flush=True)
temporary = path.with_suffix('.tmp')
temporary.write_text(json.dumps(manifest, separators=(',', ':')), encoding='utf-8')
temporary.replace(path)
print('Baked original lottery frames:', sum(c['duration'] for c in manifest['clips'].values()))
