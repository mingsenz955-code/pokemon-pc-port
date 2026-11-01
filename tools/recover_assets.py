"""Reproduce the source-data recovery. Keep the APK unchanged as evidence."""
import argparse
import base64
import collections
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'src'))
from csb_reader import read_csb

ALPHABET = b'ABCDEFGHIJKLmnopqrstuvwxyz01234abcdefghijklMNOPQRSTUVWXYZ+/56789'
STANDARD = b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
TRANSLATION = bytes.maketrans(ALPHABET, STANDARD)
EXPECTED_MD5 = '11423b7795ff53819f8f42d65b76455d'


def recover(apk, output, research=None):
    md5 = hashlib.md5(apk.read_bytes()).hexdigest()
    if md5 != EXPECTED_MD5:
        raise ValueError(f'Unexpected package MD5 {md5}; refusing to label it as the verified 1.20.4 candidate.')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Recovery target is not empty; choose a new directory to preserve existing assets.')
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(apk) as archive:
        for member in archive.infolist():
            if not member.filename.startswith('assets/') or member.is_dir():
                continue
            relative = Path(member.filename)
            if '..' in relative.parts or relative.is_absolute():
                raise ValueError('Unsafe archive path')
            target = output/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(member))
        if research is not None:
            core = research/'original-core.so'
            if core.exists():
                raise ValueError('Refusing to overwrite an existing research binary')
            binaries = [name for name in archive.namelist()
                        if name in ('lib/armeabi/libcocos2dcpp.so', 'lib/armeabi-v7a/libcocos2dcpp.so')]
            if len(binaries) != 1:
                raise ValueError(f'Expected one original ARM core, found {binaries}')
            research.mkdir(parents=True, exist_ok=True)
            core.write_bytes(archive.read(binaries[0]))
    assets = output/'assets'
    data = json.loads(base64.b64decode((assets/'Data/Prototype.data').read_bytes().translate(TRANSLATION)))
    (output/'prototype.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tables = {name: {key: dict(zip(rows['columnNames'], row)) for key, row in rows.items()
                     if key != 'columnNames'} for name, rows in data.items()}
    (output/'tables.json').write_text(json.dumps(tables, ensure_ascii=False, indent=2), encoding='utf-8')
    event_dir = output/'events'
    event_dir.mkdir(exist_ok=True)
    commands = collections.Counter()
    events = 0
    for path in sorted((assets/'PlotEvent').glob('*.json')):
        event = json.loads(base64.b64decode(path.read_bytes().translate(TRANSLATION)))
        (event_dir/path.name).write_text(json.dumps(event, ensure_ascii=False, indent=2), encoding='utf-8')
        if path.name != 'pEventContents.json':
            commands.update(step.get('type', '?') for step in event)
        events += 1
    fixed = 0
    pngs = list(assets.rglob('*.png'))
    for path in pngs:
        raw = path.read_bytes()
        if raw.startswith(b'\x89ZZLT'):
            path.write_bytes(b'\x89PNG\r\n\x1a\n'+raw[5:])
            fixed += 1
        with Image.open(path) as image:
            image.verify()
    layouts = output/'ui-layouts'
    layouts.mkdir(exist_ok=True)
    for path in sorted(assets.rglob('*.csb')):
        target = layouts/(path.stem+'.json')
        if target.exists():
            raise ValueError(f'Duplicate UI layout stem: {path.stem}')
        target.write_text(json.dumps(read_csb(path), ensure_ascii=False, indent=2), encoding='utf-8')
    audit = {'source_md5': md5, 'source_sha256': hashlib.sha256(apk.read_bytes()).hexdigest(),
             'data_tables': len(tables), 'scene_configurations': len(tables['VillageMap']),
             'pet_entries': len(tables['Pet']), 'events_decoded': events, 'event_commands': commands,
             'ui_layouts_decoded': len(list(layouts.glob('*.json'))),
             'research_core_extracted': research is not None,
             'pngs_verified': len(pngs), 'image_headers_restored': fixed}
    (output/'recovery-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    return audit


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('apk', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--research-output', type=Path)
    args = parser.parse_args()
    print(json.dumps(recover(args.apk, args.output, args.research_output), ensure_ascii=False, indent=2))
