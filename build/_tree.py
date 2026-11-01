import json, sys

def walk(node, depth=0, limit=200):
    if depth > 6 or limit[0] <= 0:
        return
    limit[0] -= 1
    name = node.get('name', '')
    extra = []
    if node.get('text'):
        extra.append('text=' + node['text'])
    if node.get('resource', {}).get('path'):
        extra.append('res=' + node['resource']['path'])
    if node.get('size'):
        extra.append('size=' + str(node['size']))
    if node.get('position'):
        extra.append('pos=' + str(node['position']))
    print('  '*depth + f"{node.get('class')} [{name}] " + ' '.join(extra))
    for c in node.get('children', []):
        walk(c, depth+1, limit)

for name in sys.argv[1:]:
    print('='*30, name)
    layout = json.load(open('original-1.20.4/ui-layouts/' + name + '.json', encoding='utf-8'))
    walk(layout['tree'], 0, [300])