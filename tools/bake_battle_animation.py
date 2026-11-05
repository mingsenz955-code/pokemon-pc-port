"""Cache original 60 Hz skill layers at the battle's 960x576 display scale."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from armature_composite import transform_art
from battle_animation_cache import NAMES, REVISION, load_manifest
from animation_cache import fingerprint

data = OriginalData(ROOT/'x-data')
output = ROOT/'generated-assets/battle'
output.mkdir(parents=True, exist_ok=True)
existing = load_manifest(data)
if existing and existing[0].resolve() == output.resolve():
    complete = all((output/name/filename).is_file()
                   for name, frames in existing[1]['frames'].items()
                   for frame in frames if frame
                   for filename, _, _ in frame[2])
    if complete:
        print('Original layered battle cache is current.')
        raise SystemExit(0)
manifest = {'revision': REVISION, 'scale': 1.2, 'sources': {}, 'frames': {}}
for name in NAMES:
    folder, source = data.armature_source(name)
    manifest['sources'][name] = fingerprint(folder, name)
    move = next(m for m in source['animation_data'][0]['mov_data'] if m['name'] == 'Animation1')
    frames = []
    target = output/name
    target.mkdir(parents=True, exist_ok=True)
    for index in range(int(move['dr'])):
        art = data.armature(name, 'Animation1', index, layered=True)
        if art is None:
            frames.append(None)
        else:
            art = transform_art(art, 1.2)
            layers = []
            for layer_index, (layer, offset, additive) in enumerate(art.info['blend_layers']):
                filename = f'{index}-{layer_index}.png'
                layer.save(target/filename, compress_level=1)
                layers.append([filename, offset, additive])
            frames.append([art.size, art.info['origin'], layers])
        data._render_armature.cache_clear()
        if index % 60 == 0:
            print(name, index, '/', move['dr'], flush=True)
    manifest['frames'][name] = frames
temporary = output/'manifest.tmp'
temporary.write_text(json.dumps(manifest, separators=(',', ':')), encoding='utf-8')
temporary.replace(output/'manifest.json')
print('Battle cache ready:', sum(len(v) for v in manifest['frames'].values()), 'frames')
