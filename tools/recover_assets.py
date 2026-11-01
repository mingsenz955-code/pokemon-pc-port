"""Reproduce the source-data recovery. Keep the APK unchanged as evidence."""
import argparse
import base64
import collections
import hashlib
import json
import zipfile
from pathlib import Path

from PIL import Image

ALPHABET = b'ABCDEFGHIJKLmnopqrstuvwxyz01234abcdefghijklMNOPQRSTUVWXYZ+/56789'
STANDARD = b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
TRANSLATION = bytes.maketrans(ALPHABET, STANDARD)
EXPECTED_MD5 = '11423b7795ff53819f8f42d65b76455d'


def recover(apk, output):
    md5 = hashlib.md5(apk.read_bytes()).hexdigest()
    if md5 != EXPECTED_MD5:
        raise ValueError(f'Unexpected package MD5 {md5}; refusing to label it as the verified 1.20.4 candidate.')
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
    audit = {'source_md5': md5, 'source_sha256': hashlib.sha256(apk.read_bytes()).hexdigest(),
             'data_tables': len(tables), 'scene_configurations': len(tables['VillageMap']),
             'pet_entries': len(tables['Pet']), 'events_decoded': events, 'event_commands': commands,
             'pngs_verified': len(pngs), 'image_headers_restored': fixed}
    (output/'recovery-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    return audit


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('apk', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(recover(args.apk, args.output), ensure_ascii=False, indent=2))
