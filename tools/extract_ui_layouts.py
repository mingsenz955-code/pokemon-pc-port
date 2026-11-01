import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from csb_reader import read_csb

target = ROOT/'original-1.20.4/ui-layouts'
target.mkdir(exist_ok=True)
errors, classes, versions, count = [], {}, {}, 0
for path in sorted((ROOT/'original-1.20.4/assets').rglob('*.csb')):
    try:
        layout = read_csb(path)
        def visit(n):
            classes[n['class']] = classes.get(n['class'], 0)+1
            for c in n['children']:
                visit(c)
        visit(layout['tree'])
        versions[layout['version']] = versions.get(layout['version'], 0)+1
        (target/(path.stem+'.json')).write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding='utf-8')
        count += 1
    except Exception as error:
        errors.append([str(path.relative_to(ROOT)), type(error).__name__, str(error)])
audit = {'decoded_layouts': count, 'versions': versions, 'widget_classes': classes,
         'errors': errors, 'interactive_widget_behaviors': 'not implemented by this extractor'}
(ROOT/'outputs/verification/ui-layout-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({**audit, 'errors': errors[:5], 'error_count': len(errors)}, ensure_ascii=False, indent=2))
