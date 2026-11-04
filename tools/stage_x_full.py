"""Stage the complete recovered X 2.10.9 data as a PC data directory.

The Android package ships data, resources and a compiled Cocos2d-x engine.
This tool keeps the recovered X data authoritative and only applies structural
compatibility fixes that the PC loader needs (missing event ids, skipped
server-only trigger entries).  The 1.20.4 baseline remains available through
``original-1.20.4`` and is not modified.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))


def write_json(path: Path, value):
    """Write source data as UTF-8 JSON without depending on migration tools."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def _remove_output(output: Path):
    """Remove only this staging directory, never a linked assets source."""
    if not output.exists():
        return
    assets = output/'assets'
    if assets.exists() and assets.is_dir():
        # A development junction must be unlinked with rmdir, not recursively
        # deleted, or its target (the recovered APK assets) could be removed.
        subprocess.run(['cmd', '/c', 'rmdir', str(assets)],
                       capture_output=True, text=True, encoding='gbk', errors='replace')
    if output.exists():
        shutil.rmtree(output)


def normalize_events(source: Path, output: Path):
    """Copy X events, assigning ids to standalone talk files.

    Four pEventContents trigger entries point at scripts that exist in neither
    the APK nor the PC baseline.  They cannot be fabricated; remove only those
    contents rows and report them so a map trigger cannot crash on a missing
    server-only file.
    """
    out = output/'events'
    out.mkdir(parents=True, exist_ok=True)
    available = {p.stem for p in (source/'events').glob('*.json')}
    missing = []
    for path in sorted((source/'events').glob('*.json')):
        rows = json.loads(path.read_bytes())
        if path.name == 'pEventContents.json':
            kept = []
            for row in rows:
                if f'pEvent{row["id"]}' not in available:
                    missing.append(str(row['id']))
                else:
                    kept.append(row)
            rows = kept
        else:
            used = {row['id'] for row in rows if 'id' in row}
            free = max(used, default=0)+1
            for row in rows:
                if 'id' not in row:
                    row['id'] = free
                    free += 1
        write_json(out/path.name, rows)
    return sorted(set(missing), key=lambda value: int(value))


def extract_layouts(assets: Path, output: Path, baseline: Path):
    """Keep baseline fallbacks, then decode every X CSB over them."""
    from csb_reader import read_csb
    target = output/'ui-layouts'
    source_layouts = baseline/'ui-layouts'
    if source_layouts.is_dir():
        shutil.copytree(source_layouts, target, dirs_exist_ok=True)
    else:
        target.mkdir(parents=True, exist_ok=True)
    errors, count = [], 0
    for path in sorted((assets/'res/UI').glob('*.csb')):
        try:
            write_json(target/(path.stem+'.json'), read_csb(path))
            count += 1
        except Exception as error:  # noqa: BLE001 - report the actual bad node
            errors.append({'file': path.name, 'error': f'{type(error).__name__}: {error}'})
    return count, errors


def stage_full(source: Path, baseline: Path, output: Path, *, link_assets=False):
    assets = source/'assets'
    _remove_output(output)
    output.mkdir(parents=True)
    if link_assets:
        # Windows normally allows directory junctions without elevation even
        # when symlink creation is disabled; fall back to a full copy.
        target = output/'assets'
        made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(target.resolve()), str(assets.resolve())],
                              capture_output=True, text=True, encoding='gbk', errors='replace')
        if made.returncode != 0:
            shutil.copytree(assets, target)
    else:
        shutil.copytree(assets, output/'assets')
    tables = json.loads((source/'tables.json').read_bytes())
    write_json(output/'tables.json', tables)
    missing = normalize_events(source, output)
    layouts, layout_errors = extract_layouts(assets, output, baseline)
    audit = {
        'source': str(source),
        'sha256': '054f4eeec42919c35d4527999b7a56af7755a0259b7a6fe110cc81868f1588e9',
        'assets': sum(1 for p in (output/'assets').rglob('*') if p.is_file()),
        'maps': len(tables.get('VillageMap', {})),
        'pets': len(tables.get('Pet', {})),
        'items': len(tables.get('Item', {})),
        'events': len(list((output/'events').glob('*.json'))),
        'ui_layouts': layouts,
        'ui_layout_errors': layout_errors,
        'missing_trigger_scripts': missing,
    }
    write_json(output/'x-full-audit.json', audit)
    return audit


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path, nargs='?', default=Path('research/apk-x-2.10.9'))
    parser.add_argument('output', type=Path, nargs='?', default=Path('x-data'))
    parser.add_argument('--baseline', type=Path, default=Path('original-1.20.4'))
    parser.add_argument('--link-assets', action='store_true',
                        help='Development shortcut: link assets instead of copying 400 MB.')
    args = parser.parse_args()
    result = stage_full(args.source, args.baseline, args.output, link_assets=args.link_assets)
    print(json.dumps(result, ensure_ascii=False, indent=2))