"""Build-time, lossless layered cache for expensive original skill armatures."""
import json
from functools import lru_cache
from pathlib import Path
from PIL import Image
from animation_cache import fingerprint

REVISION = 1
NAMES = ('xuanfeng', 'nengliangbaoxuan', '51_haishenhuanghun', 'skill024')


@lru_cache(maxsize=4)
def load_manifest(data):
    for root in (data.root/'cache/battle', data.root.parent/'generated-assets/battle'):
        try:
            manifest = json.loads((root/'manifest.json').read_bytes())
            if (manifest['revision'] == REVISION and all(
                    manifest['sources'][name] == fingerprint(data.armature_source(name)[0], name)
                    for name in NAMES)):
                return root, manifest
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


@lru_cache(maxsize=48)
def read_frame(root, name, index, metadata):
    size, origin, layers = json.loads(metadata)
    art = Image.new('RGBA', tuple(size))
    rendered = []
    for filename, offset, additive in layers:
        with Image.open(Path(root)/name/filename) as image:
            layer = image.convert('RGBA')
        rendered.append((layer, tuple(offset), additive))
    art.info['origin'] = tuple(origin)
    art.info['blend_layers'] = tuple(rendered)
    # Battle effects composite the ordered layers directly. The transparent
    # canvas carries size/origin without an extra flattened PNG decode.
    return art


def cached_frame(data, name, index, scale):
    if name not in NAMES or scale != 1.2 or not getattr(data, 'enable_baked', True):
        return None
    loaded = load_manifest(data)
    if loaded is None:
        return None
    root, manifest = loaded
    frames = manifest['frames'].get(name, [])
    if not 0 <= index < len(frames) or frames[index] is None:
        return None
    try:
        return read_frame(str(root), name, index, json.dumps(frames[index], separators=(',', ':')))
    except OSError:
        return None  # Missing cache files fall back to original live rendering.
