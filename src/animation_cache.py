"""Lossless original lottery frames, baked at build time to avoid runtime stalls."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from PIL import Image

REVISION = 2
NAMES = ('niudanji', 'ndchongwubeijingguang')


def fingerprint(folder, name):
    digest = hashlib.sha256(str(REVISION).encode())
    files = [folder/(name+'.ExportJson')]
    files += sorted(folder.glob(name+'[0-9]*.plist'))
    files += sorted(folder.glob(name+'[0-9]*.png'))
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


@lru_cache(maxsize=32)
def read_frame(root, name, clip, frame, origin):
    with Image.open(Path(root)/name/clip/(str(frame)+'.png')) as source:
        result = source.convert('RGBA')
    result.info['origin'] = origin
    return result


def load_manifest(data):
    for root in (data.root/'cache/lottery', data.root.parent/'generated-assets/lottery'):
        path = root/'manifest.json'
        if not path.exists():
            continue
        try:
            manifest = json.loads(path.read_text(encoding='utf-8'))
            if manifest['revision'] != REVISION:
                continue
            if all(manifest['sources'][name] == fingerprint(data.armature_source(name)[0], name) for name in NAMES):
                return root, manifest
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None
