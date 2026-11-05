"""Verify staged resources against the user's APK, without modifying either."""
import base64
import collections
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from battle_effects import BattleEffects

APK = Path(r'C:/Users/Mingsen/Downloads/口袋妖怪X_2.10.9.apk.1')
OUT = ROOT/'outputs/verification/0.2.97'
OUT.mkdir(parents=True, exist_ok=True)
translation = bytes.maketrans(b'ABCDEFGHIJKLmnopqrstuvwxyz01234abcdefghijklMNOPQRSTUVWXYZ+/56789',
                            b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/')
report = {'apk_sha256': hashlib.file_digest(APK.open('rb'), 'sha256').hexdigest()}
with zipfile.ZipFile(APK) as archive:
    unchanged = restored = 0
    missing, changed = [], []
    for member in archive.infolist():
        if not member.filename.startswith('assets/') or member.is_dir():
            continue
        raw = archive.read(member)
        repaired = b'\x89PNG\r\n\x1a\n'+raw[5:] if raw.startswith(b'\x89ZZLT') else raw
        path = ROOT/'x-data'/member.filename
        if not path.is_file():
            missing.append(member.filename)
        elif path.read_bytes() != repaired:
            changed.append(member.filename)
        elif raw == repaired:
            unchanged += 1
        else:
            restored += 1
    raw = archive.read('assets/Data/Prototype.data')
    prototype = json.loads(raw if raw.lstrip().startswith(b'{') else base64.b64decode(raw.translate(translation)))
    tables = {name: {key: dict(zip(rows['columnNames'], row)) for key, row in rows.items()
                     if key != 'columnNames'} for name, rows in prototype.items()}
    staged = json.loads((ROOT/'x-data/tables.json').read_bytes())
    report.update(assets_identical=unchanged, png_headers_restored=restored,
                  missing_assets=missing, changed_assets=changed,
                  table_differences=[k for k in tables if tables[k] != staged.get(k)])
data = OriginalData(ROOT/'x-data')
effects = BattleEffects(data)
counts, absent, easing_types, blend_types = collections.Counter(), [], collections.Counter(), collections.Counter()
for key, skill in data.tables['Skill'].items():
    row = data.tables['SkillEffect'].get(skill.get('skillEffectTypeId'))
    if not row:
        continue
    plan = effects.plan(key, 'player')
    if not plan:
        absent.append(key)
    else:
        counts[str(plan['type'])] += 1
for path in (data.assets/'Skill').glob('*.ExportJson'):
    source = json.loads(path.read_bytes())
    for animation in source.get('animation_data', []):
        for move in animation.get('mov_data', []):
            for bone in move.get('mov_bone_data', []):
                for frame in bone.get('frame_data', []):
                    easing_types[str(frame.get('twE', 0))] += 1
                    blend_types[str(frame.get('bd_dst', 771))] += 1
report.update(skill_plans_by_type=counts, missing_skill_plans=absent,
              skill_easing_frames=easing_types, skill_blend_frames=blend_types,
              scope='Resource identity and configuration audit; not Android/PC visual or full-playthrough parity.')
(OUT/'apk-comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=True, indent=2))
