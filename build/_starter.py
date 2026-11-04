import json
for name in ['pEvent5801002.json', 'pEvent5801003.json', 'pEvent5801004.json']:
    print('====', name)
    for step in json.load(open('original-1.20.4/events/'+name, encoding='utf-8')):
        print(step)